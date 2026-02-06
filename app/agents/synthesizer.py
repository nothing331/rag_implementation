"""
Synthesizer Agent - Generates final response with citations.
"""
from typing import List, AsyncGenerator, Union
import groq
from app.config import get_settings
from app.agents.validator import ValidatedChunk


class SynthesizerAgent:
    """Agent that synthesizes validated chunks into a coherent response."""
    
    def __init__(self):
        """Initialize with Groq client."""
        settings = get_settings()
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.model = settings.synthesizer_model
        self.temperature = settings.synthesizer_temperature
    
    async def synthesize(
        self,
        query: str,
        validated_chunks: List[ValidatedChunk],
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate final response from validated chunks.
        
        Args:
            query: Original user query
            validated_chunks: Validated chunks sorted by confidence
            stream: Whether to stream the response
            
        Returns:
            Either complete string or async generator for streaming
        """
        # Build context from validated chunks
        context = self._build_context(validated_chunks)
        
        # Build prompt
        prompt = self._build_prompt(query, context, validated_chunks)
        
        if stream:
            return self._generate_stream(prompt)
        else:
            return await self._generate_complete(prompt)
    
    def _build_context(self, validated_chunks: List[ValidatedChunk]) -> str:
        """Build context string from validated chunks."""
        context_parts = []
        
        for i, vc in enumerate(validated_chunks[:5], 1):  # Top 5 chunks
            chunk = vc.chunk
            context_parts.append(
                f"[{i}] Document: {chunk.document} (Section: {chunk.section})\n"
                f"Relevance: {vc.confidence:.2f}\n"
                f"Content: {chunk.content}\n"
            )
        
        return "\n---\n".join(context_parts)
    
    def _build_prompt(
        self,
        query: str,
        context: str,
        validated_chunks: List[ValidatedChunk]
    ) -> str:
        """Build the synthesis prompt."""
        return f"""You are a helpful technical documentation assistant. Answer the user's question based on the provided context.

User Question: {query}

Context from documentation:
{context}

Instructions:
1. Answer directly based ONLY on the provided context
2. Use citation markers like [1], [2], etc. when referencing specific information
3. Be concise but complete
4. If information is missing, say so explicitly
5. Structure the answer with clear steps or points where applicable

Format your response with inline citations. Example: "To deploy [1], you need to build the Docker image first [2]."

Answer:"""
    
    async def _generate_complete(self, prompt: str) -> str:
        """Generate complete response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation assistant. Provide accurate, well-cited answers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    async def _generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation assistant. Provide accurate, well-cited answers."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=2000,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            yield f"Error in stream: {str(e)}"
