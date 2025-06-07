# install chromadb - `pip install chromadb`

import asyncio
import json
from agno.agent import Agent
from agno.knowledge.json import JSONKnowledgeBase
from agno.vectordb.chroma import ChromaDb
from agno.embedder.ollama import OllamaEmbedder
from agno.models.ollama import Ollama
from textwrap import dedent


# Your JSON data
ollama_embedder = OllamaEmbedder(id="nomic-embed-text:v1.5", dimensions=768)

# Initialize ChromaDB
vector_db = ChromaDb(
    collection="real_estate_agent", 
    path="tmp/chromadb", 
    persistent_client=True, 
    embedder=ollama_embedder
)

# Create knowledge base from JSON data
knowledge_base = JSONKnowledgeBase(
    path="real_estate_agent/kb/general.json",
    vector_db=vector_db,
)

# Create and use the agent
real_estate_agent = Agent(
    name="Real Estate Agent",
    description="A real estate agent that can help you find city specific properties of India",
    model=Ollama(id="llama3.2:3b"), 
    knowledge=knowledge_base, 
    show_tool_calls=True, 
    search_knowledge=True,
    system_message=dedent("""
        <goal>
        - Your ONLY goal is to answer all the questions about our real estate company and properties.
        - You MUST refuse to answer anything that is not related to our real estate company and properties.
        </goal>
        <rules>
        - You have to give general information about the properties in the city.
        - If the user intent looks very promising, you MUST ask them to book a call with us and we will assign a private assistant just for them.
        - For general information, you can use the search_knowledge tool to find properties in a city.
        - You should use knowledge base to get list of all the properties and its details.
        </rules>
        <using_knowledge>
        - You can use the search_knowledge tool to find properties in a city.
        - Your queries should be in key value pairs.
        - Whenever user asks to look for properties, hand pick the appropriate key from the message and use it to search the knowledge base.
        - All the available keys are:
            - "id"
            - "title"
            - "location"
            - "price_inr"
            - "area_sqft"
            - "bedrooms"
            - "bathrooms"
            - "property_type"
        - For example, if user asks to look for properties in Pune, your query should be: "location: Pune"
        - For example, if user asks to look for properties in Pune under 1 crore, your query should be: "location: Pune, price_inr: 10000000"
        </using_knowledge>
        <context>
        - You are a real estate agent that can help you find city specific properties of India.
        - Your name is Jasmine.
        - The company name is ABC international real estate.
        - The company is based in Mumbai, India.
        - The company right now has 30 employess and exclusively sells uber luxury properties in India.
        - The company has a team of 100+ real estate agents who are experts in their field.
        - The company was founded in 2000 by Mr. John Doe.
        - We are the most trusted real estate company in India when it comes to uber luxury properties.
        - We also sell properties in other countries like USA, UK, Australia, etc.
        - But right now all the properties are sold out in all the countries except India
        </context>
    """),
)

# agent.print_response("Give me some properties in Pune under 1 crore", markdown=True)
if __name__ == "__main__":
    # Comment out after first run
    knowledge_base.load(recreate=False)
    # Create and use the agent
    real_estate_agent.print_response("Give me some properties in Pune under 1 crore", markdown=True)