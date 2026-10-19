import json

class ResultLogger:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def log_result(self, image_path: str, result: dict):
        with open(self.file_path, "a") as f:
            json.dump({"image": image_path, "result": result}, f)
            f.write("\n")
