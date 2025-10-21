from transformers import PegasusTokenizer, PegasusForConditionalGeneration

# Choose the Pegasus model you want to download
model_name = "google/pegasus-xsum"

# Directory where the model will be saved
save_directory = "./model/pegasus-xsum-local"

# Load the model and tokenizer from Hugging Face
tokenizer = PegasusTokenizer.from_pretrained(model_name)
model = PegasusForConditionalGeneration.from_pretrained(model_name)

# Save them locally
tokenizer.save_pretrained(save_directory)
model.save_pretrained(save_directory)

print(f"Pegasus model saved locally at: {save_directory}")
