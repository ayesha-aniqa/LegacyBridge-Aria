import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(
    project="legacybridge-hackathon",
    location="us-east4"
)

model=GenerativeModel("gemini-2.0-flash")

response=model.generate_content("create a beautifull stanza from youself of urdu")

print("Api is working")
print("Response ", response.text)