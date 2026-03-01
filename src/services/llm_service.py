# src/services/llm_service.py
from typing import List, Dict, Any, Optional

import asyncio

try:
    from groq import Groq
except Exception:  # pragma: no cover
    Groq = None  # type: ignore[assignment]

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
except Exception:  # pragma: no cover
    HuggingFaceEmbeddings = None  # type: ignore[assignment]

try:
    from langchain_community.vectorstores import Redis
except Exception:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

from src.core.config import settings
from src.services.monitoring import logger

class LLMService:
    """LLM integration for advanced AI capabilities"""
    
    def __init__(self):
        self.client = None
        self.embeddings = None
        self.vector_store = None

        self.model_name = settings.GROQ_MODEL
        self.temperature = settings.GROQ_TEMPERATURE

        if Groq is None:
            logger.warning("Groq client not available; LLM features will be disabled")
            return

        if not settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY is not set; LLM features will be disabled")
            return

        self.client = Groq(api_key=settings.GROQ_API_KEY)

        if HuggingFaceEmbeddings is None:
            logger.warning("HuggingFaceEmbeddings not available; FAQ retrieval disabled")
            return

        try:
            self.embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)
        except (ImportError, OSError) as e:
            logger.warning("HuggingFace embeddings could not be loaded; FAQ retrieval disabled: %s", e)
            self.embeddings = None

        if Redis is None or self.embeddings is None:
            logger.warning("Redis vectorstore not available; FAQ retrieval disabled")
            return

        self.vector_store = Redis(
            redis_url=settings.REDIS_URL,
            index_name="faq_embeddings",
            embedding=self.embeddings,
        )
        
        # Conversation memories
        self.memories: Dict[str, List[Dict[str, str]]] = {}
    
    async def initialize_faq_store(self, faqs: List[Dict]):
        """Initialize vector store with FAQs"""
        if self.vector_store is None:
            raise RuntimeError("Vector store not initialized")

        texts = [f"{faq['question']} {faq['answer']}" for faq in faqs]
        metadatas = [{"category": faq["category"], "faq_id": faq["id"]} for faq in faqs]
        
        await self.vector_store.aadd_texts(texts, metadatas)
        logger.info(f"Initialized FAQ store with {len(faqs)} entries")
    
    async def semantic_search(self, query: str, k: int = 3) -> List[Dict]:
        """Semantic search for relevant FAQs"""
        if self.vector_store is None:
            return []

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
        if self.client is None:
            return {
                "answer": "LLM is not configured.",
                "source_documents": [],
                "sentiment": {
                    "sentiment": "neutral",
                    "urgency": "low",
                    "emotion": "unknown",
                    "score": 0.0,
                },
                "conversation_id": user_id,
            }

        # Get or create conversation memory
        if user_id not in self.memories:
            self.memories[user_id] = []

        # Search for relevant FAQs (optional)
        source_documents: List[Dict[str, Any]] = []
        if self.vector_store is not None:
            try:
                source_documents = await self.semantic_search(query)
            except Exception:
                source_documents = []

        context_blurb = ""
        if context:
            try:
                context_blurb = "\n".join([str(item) for item in context])
            except Exception:
                context_blurb = ""

        sources_blurb = ""
        if source_documents:
            sources_blurb = "\n".join(
                [
                    f"- {doc.get('content','')}"
                    for doc in source_documents
                    if isinstance(doc, dict)
                ]
            )

        system_prompt = (
            "You are a helpful campus customer support assistant. "
            "Answer clearly and concisely. "
            "If you are unsure, say so and suggest creating a support ticket."
        )

        user_prompt_parts = [f"User question: {query}"]
        if context_blurb:
            user_prompt_parts.append(f"Additional context:\n{context_blurb}")
        if sources_blurb:
            user_prompt_parts.append(f"Relevant knowledge base snippets:\n{sources_blurb}")
        user_prompt = "\n\n".join(user_prompt_parts)

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(self.memories[user_id][-10:])
        messages.append({"role": "user", "content": user_prompt})

        def _do_call() -> str:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                timeout=settings.LLM_TIMEOUT,
            )
            content = completion.choices[0].message.content
            return content or ""

        try:
            answer = await asyncio.wait_for(
                asyncio.to_thread(_do_call),
                timeout=float(settings.LLM_TIMEOUT) + 5,
            )
        except asyncio.TimeoutError:
            logger.warning("LLM call timed out")
            answer = "The request took too long. Please try again."

        self.memories[user_id].append({"role": "user", "content": query})
        if answer:
            self.memories[user_id].append({"role": "assistant", "content": answer})
        
        # Analyze sentiment
        sentiment = await self.analyze_sentiment(query)
        
        return {
            "answer": answer,
            "source_documents": source_documents,
            "sentiment": sentiment,
            "conversation_id": user_id
        }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of user message"""
        if self.client is None:
            return {
                "sentiment": "neutral",
                "urgency": "low",
                "emotion": "unknown",
                "score": 0.5,
            }

        prompt = (
            "Analyze the sentiment of this text and return a JSON with:"
            "\n- sentiment: positive, negative, or neutral"
            "\n- urgency: low, medium, high, or urgent"
            "\n- emotion: primary emotion detected"
            "\n- score: confidence score 0-1"
            f"\n\nText: {text}\n\nReturn only the JSON."
        )

        def _do_call() -> str:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a sentiment analysis assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            content = completion.choices[0].message.content
            return content or ""

        result_text = await asyncio.to_thread(_do_call)
        
        try:
            import json
            return json.loads(result_text)
        except:
            return {
                "sentiment": "neutral",
                "urgency": "low",
                "emotion": "unknown",
                "score": 0.5
            }
    
    async def summarize_ticket(self, ticket_id: int, messages: List[str]) -> str:
        """Summarize support ticket conversation"""
        if self.client is None:
            return ""

        conversation = "\n".join(messages)
        
        prompt = (
            "Summarize this support ticket conversation in 3 bullet points:\n"
            "- Main issue\n"
            "- Actions taken\n"
            "- Current status\n\n"
            f"Conversation:\n{conversation}\n\nSummary:"
        )

        def _do_call() -> str:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You summarize support conversations."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content = completion.choices[0].message.content
            return content or ""

        return await asyncio.to_thread(_do_call)
    
    async def predict_ticket_category(self, description: str) -> str:
        """Predict ticket category using LLM"""
        if self.client is None:
            return "other"

        prompt = (
            "Categorize this support ticket into one of:\n"
            "- scheduling\n"
            "- equipment\n"
            "- facilities\n"
            "- energy\n"
            "- account\n"
            "- other\n\n"
            f"Description: {description}\n\nCategory:"
        )

        def _do_call() -> str:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You classify support tickets."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            content = completion.choices[0].message.content
            return content or ""

        result_text = await asyncio.to_thread(_do_call)
        return result_text.strip().lower()

    async def generate_auto_response(self, ticket_data: Dict) -> str:
        """Generate automatic response for common issues"""
        if self.client is None:
            return ""

        category = str(ticket_data.get("category", "other"))
        description = str(ticket_data.get("description", ""))

        prompt = (
            "Generate a helpful automatic response for this support ticket. "
            "Be empathetic and provide clear next steps.\n\n"
            f"Category: {category}\n"
            f"Description: {description}\n\n"
            "Response:"
        )

        def _do_call() -> str:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You write customer support replies."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
            )
            content = completion.choices[0].message.content
            return content or ""

        return await asyncio.to_thread(_do_call)