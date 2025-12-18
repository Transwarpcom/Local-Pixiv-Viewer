import os
import numpy as np
import onnxruntime as ort
from PIL import Image
from huggingface_hub import hf_hub_download
import csv
import jieba.analyse
from app.services.translator import translator

class ImageTagger:
    def __init__(self):
        self.model_repo = "SmilingWolf/wd-v1-4-moat-tagger-v2"
        self.model_filename = "model.onnx"
        self.tags_filename = "selected_tags.csv"
        self.model_path = None
        self.tags_path = None
        self.tags = []
        self.model = None

    def load(self):
        if self.model:
            return

        try:
            print("Loading Tagger Model...")
            # Download/Cache Model
            self.model_path = hf_hub_download(repo_id=self.model_repo, filename=self.model_filename)
            self.tags_path = hf_hub_download(repo_id=self.model_repo, filename=self.tags_filename)

            # Load ONNX Session
            self.model = ort.InferenceSession(self.model_path, providers=['CPUExecutionProvider'])

            # Load Tags
            self.tags = []
            with open(self.tags_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader) # Skip header
                for row in reader:
                    self.tags.append(row[1]) # row[1] is name usually
            print("Tagger Model Loaded.")
        except Exception as e:
            print(f"Failed to load image tagger: {e}")

    def preprocess(self, image: Image.Image):
        # WD14 usually expects 448x448, BGR, normalized
        size = 448
        img = image.convert("RGB").resize((size, size), Image.Resampling.BICUBIC)

        arr = np.array(img).astype(np.float32)
        # RGB -> BGR
        arr = arr[:, :, ::-1]

        # Batch dimension
        arr = np.expand_dims(arr, 0)
        return arr

    def tag_image(self, image_path, threshold=0.35):
        if not self.model:
            self.load()
        if not self.model:
            return ["model_error"]

        try:
            with Image.open(image_path) as img:
                input_tensor = self.preprocess(img)

            input_name = self.model.get_inputs()[0].name
            probs = self.model.run(None, {input_name: input_tensor})[0][0]

            # Get tags
            detected_tags = []

            for i, p in enumerate(probs):
                if p > threshold:
                    if i < len(self.tags):
                        tag_name = self.tags[i]
                        # Translate if possible
                        translated = translator.translate(tag_name)
                        detected_tags.append(translated)

            return detected_tags
        except Exception as e:
            print(f"Tagging failed: {e}")
            return ["error"]

class TextTagger:
    def tag_text(self, text_content, top_k=10):
        # Use Jieba TF-IDF
        tags = jieba.analyse.extract_tags(text_content, topK=top_k)
        return tags

image_tagger = ImageTagger()
text_tagger = TextTagger()
