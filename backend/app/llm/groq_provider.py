from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from app.core.config import settings
from app.llm.prompts import ANSWER_SYSTEM_PROMPT, QUERY_REWRITE_SYSTEM_PROMPT
from app.llm.provider import LlmProvider


class GroqLlmProvider(LlmProvider): 
    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise ValueError("Groq API Key is required to generate answers.")
        
        self.llm = ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.llm_model_name,
            temperature=0
        )
        
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", ANSWER_SYSTEM_PROMPT),
                (
                    "human",
                    "Question:\n{question}\n\nContext:\n{context}"
                ),
            ]  
        )
        
        self.query_rewrite_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", QUERY_REWRITE_SYSTEM_PROMPT),
                ("human", "Student question:\n{question}"),
            ]
        )
        
    def generate_answer(self, question: str, context: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be empty")
        
        if not context.strip():
            return "The student manual does not provide enough information to answer that."
        
        chain = self.prompt | self.llm
        response = chain.invoke(
            {
                "question": question,
                "context": context,
            }
        )

        return response.content.strip()

    def rewrite_query(self, question: str) -> str:
        if not question.strip():
            raise ValueError("Question must not be empty")

        chain = self.query_rewrite_prompt | self.llm
        response = chain.invoke({"question": question})
        rewritten_query = response.content.strip()

        return rewritten_query or question

