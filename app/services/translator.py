import csv
import os
import json
import httpx
from flask import current_app

class TagTranslator:
    def __init__(self):
        self.en_to_zh = {}
        self.zh_to_en = {}
        self.loaded = False
        self.cache_path = os.path.join("models", "zh_tags.json")

        # Embedded fallback dictionary (Top Danbooru tags)
        self.fallback_map = {
            "1girl": "1个女孩", "solo": "单人", "long_hair": "长发", "short_hair": "短发",
            "blue_eyes": "蓝眼", "red_eyes": "红眼", "black_hair": "黑发", "blonde_hair": "金发",
            "smile": "微笑", "open_mouth": "张嘴", "hat": "帽子", "scenery": "风景",
            "outdoors": "户外", "indoors": "室内", "day": "白天", "night": "夜晚",
            "water": "水", "sky": "天空", "cloud": "云", "flower": "花", "tree": "树",
            "building": "建筑", "ruins": "废墟", "mountain": "山", "ocean": "海洋",
            "beach": "海滩", "signature": "签名", "watermark": "水印", "explicit": "R-18",
            "censored": "打码", "monochrome": "单色", "comic": "漫画", "greyscale": "灰度",
            "abs": "腹肌", "breasts": "乳房", "nipples": "乳头", "pussy": "阴户",
            "penis": "阴茎", "sex": "性爱", "cum": "精液", "mosaic_censoring": "马赛克",
            "bar_censoring": "条形码", "twintails": "双马尾", "ponytail": "马尾",
            "blush": "脸红", "looking_at_viewer": "看镜头", "shirt": "衬衫",
            "skirt": "裙子", "dress": "连衣裙", "bikini": "比基尼", "swimsuit": "泳装",
            "lingerie": "内衣", "underwear": "内裤", "panties": "内裤", "bra": "胸罩",
            "thighhighs": "过膝袜", "gloves": "手套", "glasses": "眼镜",
            "animal_ears": "兽耳", "cat_ears": "猫耳", "fox_ears": "狐耳", "tail": "尾巴",
            "wings": "翅膀", "weapon": "武器", "sword": "剑", "gun": "枪",
            "original": "原创", "touhou": "东方Project", "fate/grand_order": "FGO",
            "genshin_impact": "原神", "azur_lane": "碧蓝航线", "kantai_collection": "舰C",
            "blue_archive": "蔚蓝档案", "uma_musume_pretty_derby": "赛马娘",
            "hololive": "Hololive", "virtual_youtuber": "虚拟主播"
        }
        self.en_to_zh.update(self.fallback_map)
        self.zh_to_en.update({v: k for k, v in self.fallback_map.items()})

        # Try to load cache immediately
        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.en_to_zh.update(data)
                    self.zh_to_en.update({v: k for k, v in data.items()})
                self.loaded = True
            except Exception as e:
                print(f"Error loading translation cache: {e}")

    def download_full_dictionary(self):
        """Downloads EhTagTranslation database from GitHub/CDN."""
        url = "https://github.com/EhTagTranslation/Database/releases/latest/download/db.text.json"
        print(f"Downloading translation database from {url}...")
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=30.0) as r:
                if r.status_code == 200:
                    content = r.read()
                    data = json.loads(content)

                    # Parse EhTag format
                    # Structure: {"data": [{"namespace": "...", "data": {"tag": {"name": "..."}}}]}
                    new_map = {}
                    for ns_item in data.get('data', []):
                        for tag_key, tag_info in ns_item.get('data', {}).items():
                            name = tag_info.get('name')
                            if name:
                                new_map[tag_key] = name

                    # Update and save cache
                    self.en_to_zh.update(new_map)
                    self.zh_to_en.update({v: k for k, v in new_map.items()})

                    os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
                    with open(self.cache_path, 'w', encoding='utf-8') as f:
                        json.dump(new_map, f, ensure_ascii=False)

                    self.loaded = True
                    print(f"Translation database updated: {len(new_map)} tags.")
                    return True
                else:
                    print(f"Failed to download dictionary: {r.status_code}")
        except Exception as e:
            print(f"Error downloading dictionary: {e}")
        return False

    def translate(self, tag):
        # Normalize
        tag = tag.strip().replace('_', ' ')
        # Check direct match
        if tag in self.en_to_zh:
            return self.en_to_zh[tag]
        # Check underscore version (if dict uses underscores)
        # EhTagTranslation usually uses space for some, underscore for others?
        # Typically Danbooru uses underscores. EhTag uses space in 'name'? No, 'key' is tag.
        # Key in EhTag JSON usually matches raw tag (often space separated for multi-word in text db? or underscore?)
        # Let's try underscore version too.
        tag_u = tag.replace(' ', '_')
        if tag_u in self.en_to_zh:
            return self.en_to_zh[tag_u]

        # Try converting input with underscores to space
        tag_s = tag.replace('_', ' ')
        if tag_s in self.en_to_zh:
            return self.en_to_zh[tag_s]

        return tag

    def translate_list(self, tags_str):
        if not tags_str:
            return ""
        # Split by comma first
        tags = [t.strip() for t in tags_str.split(',')]
        translated = [self.translate(t) for t in tags if t]
        return ",".join(translated)

translator = TagTranslator()
