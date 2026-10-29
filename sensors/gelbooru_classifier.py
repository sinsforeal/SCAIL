import os
import json

import atomic
import urllib.request
import urllib.parse
import logger


class GelbooruClassifier:
    def __init__(self, config):
        self.config = config
        self.api_key = config.gelbooru_api_key
        self.user_id = config.gelbooru_user_id
        self.request_delay = config.gelbooru_request_delay
        self.cache_path = config.gelbooru_cache_path

        self._ratings = {}
        self._ground_truth = None
        self._cleaned_groups = None
        self._disk_cache = {}

        self._load_data_files()
        self._load_disk_cache()

    def _load_data_files(self):
        ratings_path = self.config.gelbooru_ratings_json_path
        if ratings_path and os.path.exists(ratings_path):
            try:
                with open(ratings_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._ratings = data.get("ratings", {})
                logger.log(f"[GELBOORU] Loaded {len(self._ratings)} tag ratings.")
            except Exception as e:
                logger.log(f"[GELBOORU ERROR] Failed to load ratings: {e}")

        gt_path = self.config.gelbooru_ground_truth_json_path
        if gt_path and os.path.exists(gt_path):
            try:
                with open(gt_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._ground_truth = data.get("tags", {})
                logger.log(f"[GELBOORU] Loaded {len(self._ground_truth)} ground truth tags.")
            except Exception as e:
                logger.log(f"[GELBOORU ERROR] Failed to load ground truth: {e}")

        cleaned_path = self.config.gelbooru_cleaned_json_path
        if cleaned_path and os.path.exists(cleaned_path):
            try:
                with open(cleaned_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._cleaned_groups = data.get("groups", {})
                logger.log(f"[GELBOORU] Loaded {len(self._cleaned_groups)} cleaned concept groups.")
            except Exception as e:
                logger.log(f"[GELBOORU ERROR] Failed to load cleaned groups: {e}")

    def _load_disk_cache(self):
        if not self.cache_path:
            return
        if not os.path.exists(self.cache_path):
            self._disk_cache = {}
            return
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                self._disk_cache = json.load(f)
            logger.log(f"[GELBOORU] Loaded {len(self._disk_cache)} cached classifications from disk.")
        except Exception as e:
            logger.log(f"[GELBOORU ERROR] Cache load failed: {e}")
            self._disk_cache = {}

    def _save_disk_cache(self):
        if not self.cache_path:
            return
        try:
            atomic.write_json(self.cache_path, self._disk_cache)
        except Exception as e:
            logger.log(f"[GELBOORU ERROR] Cache save failed: {e}")

    def classify_by_md5(self, md5):
        if md5 in self._disk_cache:
            cached = self._disk_cache[md5]
            if cached is None:
                return None
            return cached

        post = self._fetch_post(md5)
        if not post:
            self._disk_cache[md5] = None
            self._save_disk_cache()
            return None

        raw_tags = post.get("tags", "").split()
        gelbooru_rating = post.get("rating", "unknown")

        classified = self._classify_tags(raw_tags)
        local_score = self._compute_local_score(classified)

        result = {
            "md5": md5,
            "gelbooru_rating": gelbooru_rating,
            "characters": classified["character_tags"],
            "copyrights": classified["copyright_tags"],
            "wholesome_tags": classified["wholesome_tags"],
            "unwholesome_tags": classified["unwholesome_tags"],
            "neutral_tags": classified["neutral_tags"],
            "local_score": local_score
        }

        self._disk_cache[md5] = result
        self._save_disk_cache()
        return result

    def _fetch_post(self, md5):
        query = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",
            "tags": f"md5:{md5}"
        }

        if self.api_key:
            query["api_key"] = self.api_key
        if self.user_id:
            query["user_id"] = self.user_id

        url = f"https://gelbooru.com/index.php?{urllib.parse.urlencode(query)}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "post" in data and isinstance(data["post"], list) and data["post"]:
                    return data["post"][0]
                elif isinstance(data, list) and data:
                    return data[0]
                return None
        except Exception as e:
            logger.log(f"[GELBOORU] Fetch failed for {md5[:12]}...: {type(e).__name__}")
            return None

    def _classify_tags(self, raw_tags):
        results = {
            "wholesome_tags": [],
            "unwholesome_tags": [],
            "neutral_tags": [],
            "unrated_tags": [],
            "character_tags": [],
            "copyright_tags": [],
            "metadata_tags": []
        }

        for tag in raw_tags:
            if self._ground_truth and tag in self._ground_truth:
                ttype = self._ground_truth[tag].get("ttype", 3)
                if ttype == 0:
                    results["character_tags"].append(tag)
                    continue
                elif ttype == 4:
                    results["copyright_tags"].append(tag)
                    continue
                elif ttype in (1, 2, 5):
                    results["metadata_tags"].append(tag)
                    continue

            if tag in self._ratings:
                r = self._ratings[tag]
                if r == 'W':
                    results["wholesome_tags"].append(tag)
                elif r == 'U':
                    results["unwholesome_tags"].append(tag)
                else:
                    results["neutral_tags"].append(tag)
                continue

            found = False
            if self._cleaned_groups:
                for concept, originals in self._cleaned_groups.items():
                    if tag in originals:
                        if concept in self._ratings:
                            r = self._ratings[concept]
                            if r == 'W':
                                results["wholesome_tags"].append(tag)
                            elif r == 'U':
                                results["unwholesome_tags"].append(tag)
                            else:
                                results["neutral_tags"].append(tag)
                            found = True
                        break

            if not found:
                results["unrated_tags"].append(tag)

        return results

    def _compute_local_score(self, classified):
        w = len(classified["wholesome_tags"])
        u = len(classified["unwholesome_tags"])
        total_rated = w + u

        if total_rated == 0:
            return 5.0

        ratio = w / total_rated
        return round(ratio *10.0, 2)


_READONLY = {"path": "", "mtime": 0.0, "size": -1, "data": {}}


def cached_classifications(path):
    """What the board said about the pictures he has opened. Read only.

    Keyed by the picture's own content hash and written by the classifier
    within two seconds of him opening it. A reader that only wants to NAME a
    picture (`sim/phone.py`, the trail of what he has been doing) must not
    construct `GelbooruClassifier`: that one looks a picture up over the
    network and writes this file. Nothing here writes, and nothing here asks
    the site anything. The file is re-read whenever its timestamp or its size
    changes, so a picture he opened a second ago is in it.

    The cache is the machine's rather than a character's -- its key is a
    content hash, which carries no person -- so both characters read the one
    copy of what his pictures are."""
    if not path:
        return {}
    try:
        st = os.stat(path)
    except OSError:
        return {}
    if (_READONLY["path"], _READONLY["mtime"], _READONLY["size"]) != (path, st.st_mtime, st.st_size):
        data = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except Exception as e:
            logger.log(f"[GELBOORU] read-only cache not read: {type(e).__name__}")
        _READONLY.update({"path": path, "mtime": st.st_mtime, "size": st.st_size, "data": data})
    return _READONLY["data"]
