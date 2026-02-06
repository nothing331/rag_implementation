"""
Query Planner Agent - Decomposes complex queries into sub-queries.
"""
from typing import List, Dict, Any
from dataclasses import dataclass
import json
import groq
from app.config import get_settings


@dataclass
class SubQuery:
    """A decomposed sub-query with priority."""
    text: str
    priority: int = 1
    

class QueryPlanner:
    """Agent that breaks down complex queries into parallel sub-queries."""
    
    def __init__(self):
        """Initialize with Groq client."""
        settings = get_settings()
        self.client = groq.Groq(api_key=settings.groq_api_key)
        self.model = settings.planner_model
        self.temperature = settings.planner_temperature
    
    def plan(self, query: str) -> List[SubQuery]:
        """
        Decompose a complex query into atomic, parallel sub-queries.
        
        Args:
            query: The original user query
            
        Returns:
            List of SubQuery objects that can be searched in parallel
        """
        prompt = f"""You are a Query Planning Agent. Your task is to decompose a complex user query into simple, parallel sub-queries that can be searched independently.

User Query: "{query}"

Analyze this query and break it down into 1-4 atomic sub-queries that:
1. Can be searched in parallel (no dependencies between them)
2. Are specific and focused on a single topic
3. Will help find relevant technical documentation
4. Cover all aspects of the original query

Instructions:
- Return ONLY a JSON array
- Each object must have "query" and "priority" fields
- Priority is 1 (highest) to 3 (lowest)
- Queries should be specific, not generic

Example 1:
Query: "How do I deploy to AWS with Docker?"
Response: [
  {{"query": "AWS ECS deployment prerequisites and setup", "priority": 1}},
  {{"query": "Docker image build and push to ECR", "priority": 1}},
  {{"query": "ECS task definition and service configuration", "priority": 2}}
]

Example 2:
Query: "What database does CloudSync use and how is data synchronized?"
Response: [
  {{"query": "CloudSync database technology and configuration", "priority": 1}},
  {{"query": "Data synchronization architecture and flow", "priority": 1}},
  {{"query": "Conflict resolution strategies", "priority": 2}}
]

Your response (JSON array only):
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a query planning assistant. Output only valid JSON arrays."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            
            # Parse the JSON response
            try:
                if content is None:
                    return [SubQuery(text=query, priority=1)]
                sub_queries_data = json.loads(content)
                
                # Handle both direct array and object with array
                if isinstance(sub_queries_data, list):
                    sub_queries_list = sub_queries_data
                elif isinstance(sub_queries_data, dict):
                    # Try common keys
                    for key in ["sub_queries", "queries", "results"]:
                        if key in sub_queries_data:
                            sub_queries_list = sub_queries_data[key]
                            break
                    else:
                        # If it's a dict but not recognized, treat values as queries
                        sub_queries_list = list(sub_queries_data.values()) if sub_queries_data else []
                else:
                    sub_queries_list = []
                
                # Convert to SubQuery objects
                sub_queries = []
                for sq in sub_queries_list:
                    if isinstance(sq, dict):
                        text = sq.get("query", sq.get("text", ""))
                        priority = sq.get("priority", 1)
                        if text:
                            sub_queries.append(SubQuery(text=text, priority=priority))
                
                # If parsing failed, return single query
                if not sub_queries:
                    sub_queries = [SubQuery(text=query, priority=1)]
                
                return sub_queries
                
            except json.JSONDecodeError:
                # Fallback: treat entire query as single sub-query
                return [SubQuery(text=query, priority=1)]
                
        except Exception as e:
            print(f"Error in query planning: {e}")
            return [SubQuery(text=query, priority=1)]
