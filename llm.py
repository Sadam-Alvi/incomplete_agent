import os
from langchain_core.chat_history import InMemoryChatMessageHistory, BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import List
from langchain_core.messages import BaseMessage
from langchain_huggingface import HuggingFacePipeline




hllm = HuggingFacePipeline.from_model_id(
    model_id='prism-ml/Ternary-Bonsai-2-27B-gguf',
    task='text-generation',
    pipeline_kwargs={"max_new_tokens": 128, "temperature": 0.7}
)

# 2. Wrap it in the ChatHuggingFace class (passing the correct variable)
llm = ChatHuggingFace(llm=hllm)



# ====================== CUSTOM HISTORY (keeps only last 3 pairs) ======================


class LimitedChatMessageHistory(InMemoryChatMessageHistory):
    max_pairs: int = 3   # declare it as a class field

    def __init__(self, max_pairs: int = 3):
        super().__init__()
        self.max_pairs = max_pairs

    def add_messages(self, messages: List[BaseMessage]) -> None:
        super().add_messages(messages)
        self._trim()

    def add_message(self, message: BaseMessage) -> None:
        super().add_message(message)
        self._trim()

    def _trim(self):
        max_messages = self.max_pairs * 2  # 3 pairs = 6 messages
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]
# ====================== PROMPT ======================
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant specialized in answering questions about a webpage.

Answer the user's question ONLY based on the provided page content.
If the content is insufficient, say "I don't know" or "I couldn't find that information on the page."
Do not make up answers.

Relevant page content:
{context}"""),
    
    MessagesPlaceholder(variable_name="history"),
    ("human", "{question}")
])

chain = prompt | llm

# ====================== SESSION STORE ======================
store = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = LimitedChatMessageHistory(max_pairs=3)  # ← only last 3 pairs
    return store[session_id]


chain_with_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="question",
    history_messages_key="history",
)


# ====================== MAIN FUNCTION ======================
def answer_the_given_question(question: str, context: str, session_id: str = "default") -> str:
    response = chain_with_history.invoke(
        {
            "question": question,
            "context": context
        },
        config={"configurable": {"session_id": session_id}}
    )
    return response.content