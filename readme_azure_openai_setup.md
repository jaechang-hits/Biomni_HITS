## 🔧 LLM Model Configuration & Azure OpenAI Support

This project supports multiple LLM backends (OpenAI, Azure OpenAI, Anthropic Claude, Gemini, Ollama, AWS Bedrock, and others) using a unified model-naming convention.

### ✅ How to Specify a Model

Use the `llm` argument when initializing the agent. For example:

```python
from biomni.agent import A1

# Initialize the agent with data path and Azure GPT-4o
agent = A1(path='./data', llm='azure-gpt-4o')
```

The framework will automatically infer the correct LLM backend based on the model name:

✅ For Azure, always prefix the model name with azure-, e.g., azure-gpt-4o, azure-gpt-35-turbo.


### 🛠️ Environment Setup for Azure OpenAI

To use Azure OpenAI, create a .env file in the project root with the following variables:

```
OPENAI_API_KEY=your_azure_openai_api_key
OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
```

You can find these values in the Azure OpenAI Studio.


### 🚀 Example Usage
```python
from biomni.agent import A1

# Automatically uses AzureChatOpenAI when 'azure-' prefix is detected
agent = A1(path='./data', llm='azure-gpt-4o')

# Use the agent
response = agent.query("What are the functions of p53 in DNA repair?")
print(response)
```
The system will:
	•	Detect azure- prefix
	•	Strip the prefix (azure-gpt-4o → gpt-4o)
	•	Pass the model name as Azure deployment ID
	•	Use version 2024-12-01-preview for Azure API calls


### 🔒 Notes
	•	Azure OpenAI requires the deployment name (gpt-4o, gpt-35-turbo, etc.), not the model name (gpt-4, etc.)
	•	Do not use gpt-4o without the azure- prefix unless calling the OpenAI API directly
	•	Supports fallback to other providers (Anthropic, Gemini, Ollama, etc.) based on model name heuristics

