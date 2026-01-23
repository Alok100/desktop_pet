from langchain_ollama import ChatOllama

# 1. Setup the model
llm = ChatOllama(
    model="tinyllama", #"qwen2.5:3b",
    temperature=0
)

# 2. Invoke the model with a message
response = llm.invoke("What is the time now?")

# 3. Access the content of the response
print(response.content)