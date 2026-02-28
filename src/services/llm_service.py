# src/services/llm_service.py
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Redis
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.prompts import PromptTemplate
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from typing import List, Dict, Any, Optional
import numpy as np
from src.core.config import settings
from src.services.monitoring import logger

class LLMService:
    """LLM integration for advanced AI capabilities"""
    
    def __init__(self):
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize vector store for FAQs
        self.vector_store = Redis(
            redis_url=settings.REDIS_URL,
            index_name="faq_embeddings",
            embedding_function=self.embeddings
        )
        
        # Conversation memories
        self.memories: Dict[str, ConversationBufferMemory] = {}
    
    async def initialize_faq_store(self, faqs: List[Dict]):
        """Initialize vector store with FAQs"""
        texts = [f"{faq['question']} {faq['answer']}" for faq in faqs]
        metadatas = [{"category": faq["category"], "faq_id": faq["id"]} for faq in faqs]
        
        await self.vector_store.aadd_texts(texts, metadatas)
        logger.info(f"Initialized FAQ store with {len(faqs)} entries")
    
    async def semantic_search(self, query: str, k: int = 3) -> List[Dict]:
        """Semantic search for relevant FAQs"""
        results = await self.vector_store.asimilarity_search_with_score(query, k=k)
        
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "similarity_score": float(score)
            }
            for doc, score in results
        ]
    
    async def generate_response(
        self,
        user_id: str,
        query: str,
        context: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Generate intelligent response using LLM"""
        
        # Get or create conversation memory
        if user_id not in self.memories:
            self.memories[user_id] = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
        
        memory = self.memories[user_id]
        
        # Search for relevant FAQs
        similar_faqs = await self.semantic_search(query)
        
        # Create retrieval chain
        chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vector_store.as_retriever(),
            memory=memory,
            verbose=True
        )
        
        # Generate response
        result = await chain.acall({"question": query})
        
        # Analyze sentiment
        sentiment = await self.analyze_sentiment(query)
        
        return {
            "answer": result["answer"],
            "source_documents": result.get("source_documents", []),
            "sentiment": sentiment,
            "conversation_id": user_id
        }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of user message"""
        prompt = PromptTemplate(
            input_variables=["text"],
            template="""
            Analyze the sentiment of this text and return a JSON with:
            - sentiment: positive, negative, or neutral
            - urgency: low, medium, high, or urgent
            - emotion: primary emotion detected
            - score: confidence score 0-1
            
            Text: {text}
            
            Return only the JSON.
            """
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({"text": text})
        
        try:
            import json
            return json.loads(result.content)
        except:
            return {
                "sentiment": "neutral",
                "urgency": "low",
                "emotion": "unknown",
                "score": 0.5
            }
    
    async def summarize_ticket(self, ticket_id: int, messages: List[str]) -> str:
        """Summarize support ticket conversation"""
        conversation = "\n".join(messages)
        
        prompt = PromptTemplate(
            input_variables=["conversation"],
            template="""
            Summarize this support ticket conversation in 3 bullet points:
            - Main issue
            - Actions taken
            - Current status
            
            Conversation:
            {conversation}
            
            Summary:
            """
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({"conversation": conversation})
        
        return result.content
    
    async def predict_ticket_category(self, description: str) -> str:
        """Predict ticket category using LLM"""
        prompt = PromptTemplate(
            input_variables=["description"],
            template="""
            Categorize this support ticket into one of:
            - scheduling
            - equipment
            - facilities
            - energy
            - account
            - other
            
            Description: {description}
            
            Category:
            """
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({"description": description})
        
        return result.content.strip().lower()
    
    async def generate_auto_response(self, ticket_data: Dict) -> str:
        """Generate automatic response for common issues"""
        prompt = PromptTemplate(
            input_variables=["category", "description"],
            template="""
            Generate a helpful automatic response for this support ticket.
            Be empathetic and provide clear next steps.
            
            Category: {category}
            Description: {description}
            
            Response:
            """
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke(ticket_data)
        
        return result.content