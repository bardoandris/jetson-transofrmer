from transformers import AutoModelForCausalLM
model = AutoModelForCausalLM.from_pretrained("vikhyatk/moondream2", trust_remote_code=True, device_map="auto")

