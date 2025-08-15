#!/usr/bin/env python3
"""
Vercel-compatible FastAPI application for WhatTheRepo.
Adapted for serverless deployment on Vercel.
"""

import os
import json
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymilvus import connections, Collection, utility
import openai
from openai import OpenAI
from supabase import create_client, Client
import logging

# Initialize FastAPI app
app = FastAPI(title="WhatTheRepo", description="GitHub PR analysis and insights")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="api/static"), name="static")

# Global variables
milvus_collection = None
openai_client = None
embedding_dim = 1536
engineer_lens_ui = None

# Pydantic models
class SearchRequest(BaseModel):
    query: str
    repo_name: Optional[str] = None
    limit: int = 5

class SearchResult(BaseModel):
    pr_id: int
    pr_number: int
    title: str
    content: str
    text_type: str
    file_path: str
    function_name: str
    similarity_score: float
    author: str
    created_at: int
    merged_at: int
    status: str
    is_merged: bool
    is_closed: bool
    feature: str = ""
    pr_summary: str = ""
    risk_score: float = 0.0
    risk_band: str = "low"
    risk_reasons: list = []
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    file_details: list = []

def convert_numpy_types_safe(value):
    """Convert numpy types to Python native types without importing numpy"""
    try:
        # Check if it's a numpy type by checking the type name
        type_name = type(value).__name__
        
        if type_name.startswith('int'):
            return int(value)
        elif type_name.startswith('float'):
            return float(value)
        elif type_name.startswith('bool'):
            return bool(value)
        elif hasattr(value, 'tolist'):  # numpy array
            return value.tolist()
        else:
            return value
    except Exception:
        # If conversion fails, return the original value
        return value

def initialize_connections():
    """Initialize Milvus and OpenAI connections"""
    global milvus_collection, openai_client, embedding_dim
    
    # Initialize Milvus connection
    milvus_url = os.getenv('MILVUS_URL')
    milvus_token = os.getenv('MILVUS_TOKEN')
    collection_name = os.getenv('COLLECTION_NAME', 'pr_index_what_the_repo')
    
    if not milvus_url or not milvus_token:
        print("⚠️ Milvus credentials not found - some features will be limited")
        return
    
    try:
        connections.connect(
            alias="default",
            uri=milvus_url,
            token=milvus_token
        )
        
        if not utility.has_collection(collection_name):
            print(f"⚠️ Collection '{collection_name}' does not exist")
            return
        
        milvus_collection = Collection(collection_name)
        milvus_collection.load()
        
        # Get actual dimension from collection schema
        schema = milvus_collection.schema
        for field in schema.fields:
            if field.name == "vector":
                embedding_dim = field.params.get('dim', 1536)
                break
        
        print(f"✅ Connected to Milvus collection '{collection_name}' with dimension {embedding_dim}")
        
    except Exception as e:
        print(f"❌ Failed to connect to Milvus: {e}")
    
    # Initialize OpenAI client
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        print("⚠️ OpenAI API key not found - embeddings will not work")
        return
    
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        print("✅ OpenAI client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI client: {e}")

def get_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI"""
    if not openai_client:
        raise ValueError("OpenAI client not initialized")
    
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise

# Initialize connections on startup
initialize_connections()

@app.get("/", response_class=HTMLResponse)
async def home_page():
    """Home page with repository selection and search interface"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WhatTheRepo</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                color: #ffffff;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
            }
            
            .header {
                background: rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(10px);
                padding: 2rem 0;
                text-align: center;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .header h1 {
                font-size: 3.5rem;
                font-weight: 700;
                background: linear-gradient(45deg, #00d4ff, #ff6b6b, #4ecdc4);
                background-size: 200% 200%;
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                animation: gradient 3s ease infinite;
                margin-bottom: 1rem;
            }
            
            @keyframes gradient {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }
            
            .header p {
                font-size: 1.2rem;
                color: #b0b0b0;
                max-width: 600px;
                margin: 0 auto;
                line-height: 1.6;
            }
            
            .main-content {
                flex: 1;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                padding: 4rem 2rem;
            }
            
            .content-layout {
                display: flex;
                gap: 3rem;
                align-items: flex-start;
                max-width: 1400px;
                width: 100%;
            }
            
            .repo-selector {
                background: rgba(255, 255, 255, 0.05);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                padding: 1rem 2rem;
                margin-bottom: 2rem;
                text-align: center;
                backdrop-filter: blur(10px);
                width: 100%;
                position: sticky;
                top: 0;
                z-index: 100;
            }
            
            .repo-selector h2 {
                font-size: 1.4rem;
                margin-bottom: 0.5rem;
                color: #ffffff;
                display: inline-block;
                margin-right: 1rem;
            }
            
            .select-container {
                position: relative;
                display: inline-block;
                margin-left: 1rem;
            }
            
            .repo-select {
                width: 300px;
                padding: 8px 15px;
                background: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                color: #ffffff;
                font-size: 0.9rem;
                cursor: pointer;
                transition: all 0.3s ease;
                backdrop-filter: blur(10px);
            }
            
            .repo-select:focus {
                outline: none;
                border-color: #00d4ff;
                box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
            }
            
            .search-section {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2.5rem;
                text-align: center;
                backdrop-filter: blur(10px);
                flex: 1;
                min-width: 600px;
                opacity: 0.5;
                pointer-events: none;
                transition: all 0.3s ease;
            }
            
            .search-section.active {
                opacity: 1;
                pointer-events: all;
            }
            
            .search-section h2 {
                font-size: 1.8rem;
                margin-bottom: 1.5rem;
                color: #ffffff;
            }
            
            .search-section p {
                color: #b0b0b0;
                margin-bottom: 2rem;
                line-height: 1.6;
            }
            
            .search-container {
                display: flex;
                gap: 1rem;
                margin-bottom: 2rem;
                align-items: center;
            }
            
            .search-input {
                flex: 1;
                padding: 15px 20px;
                background: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 15px;
                color: #ffffff;
                font-size: 1rem;
                transition: all 0.3s ease;
                backdrop-filter: blur(10px);
            }
            
            .search-input:focus {
                outline: none;
                border-color: #00d4ff;
                box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
            }
            
            .search-input::placeholder {
                color: #b0b0b0;
            }
            
            .search-button {
                background: linear-gradient(45deg, #00d4ff, #4ecdc4);
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 15px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                white-space: nowrap;
            }
            
            .search-button:hover {
                transform: scale(1.05);
                box-shadow: 0 10px 20px rgba(0, 212, 255, 0.3);
            }
            
            .search-button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            
            .navigation-grid {
                display: flex;
                flex-direction: column;
                gap: 2rem;
                width: 300px;
                opacity: 0.5;
                pointer-events: none;
                transition: all 0.3s ease;
            }
            
            .navigation-grid.active {
                opacity: 1;
                pointer-events: all;
            }
            
            .nav-card {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2.5rem;
                text-align: center;
                transition: all 0.3s ease;
                cursor: pointer;
                backdrop-filter: blur(10px);
                position: relative;
                overflow: hidden;
            }
            
            .nav-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
                transition: left 0.5s;
            }
            
            .nav-card:hover::before {
                left: 100%;
            }
            
            .nav-card:hover {
                transform: translateY(-10px);
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
                border-color: rgba(255, 255, 255, 0.2);
            }
            
            .nav-icon {
                font-size: 3rem;
                margin-bottom: 1.5rem;
                display: block;
            }
            
            .nav-card h2 {
                font-size: 1.8rem;
                margin-bottom: 1rem;
                color: #ffffff;
            }
            
            .nav-card p {
                color: #b0b0b0;
                line-height: 1.6;
                margin-bottom: 1.5rem;
            }
            
            .nav-button {
                background: linear-gradient(45deg, #00d4ff, #4ecdc4);
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 25px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                text-decoration: none;
                display: inline-block;
            }
            
            .nav-button:hover {
                transform: scale(1.05);
                box-shadow: 0 10px 20px rgba(0, 212, 255, 0.3);
            }
            
            .nav-button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }
            
            .footer {
                text-align: center;
                padding: 2rem;
                color: #888;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            @media (max-width: 768px) {
                .header h1 {
                    font-size: 2.5rem;
                }
                
                .content-layout {
                    flex-direction: column;
                    gap: 2rem;
                }
                
                .search-section {
                    min-width: auto;
                    width: 100%;
                }
                
                .navigation-grid {
                    width: 100%;
                    flex-direction: row;
                    justify-content: center;
                }
                
                .nav-card {
                    padding: 2rem;
                    width: 100%;
                    max-width: 300px;
                }
                
                .repo-selector {
                    padding: 2rem;
                }
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 WhatTheRepo</h1>
            <p>Discover insights from your GitHub repositories with AI-powered analysis</p>
        </div>
        
        <div class="main-content">
            <div class="repo-selector">
                <h2>Select Repository</h2>
                <div class="select-container">
                    <select id="repo-select" class="repo-select">
                        <option value="">Loading repositories...</option>
                    </select>
                </div>
            </div>
            
            <div class="content-layout">
                <div class="search-section" id="search-section">
                    <h2>Ask repo-gpt</h2>
                    <p>Ask questions about your repository's code changes, PRs, features, and more. e.g., "What was shipped in the last week?" or "Find PRs by author John Doe"</p>
                    <div class="search-container">
                        <input type="text" id="search-input" class="search-input" placeholder="e.g., 'What was shipped in the last week?'">
                        <button id="search-button" class="search-button" disabled>Search</button>
                    </div>
                    <div class="search-results" id="search-results">
                        <p class="loading">Loading example queries...</p>
                    </div>
                </div>
                
                <div class="navigation-grid" id="navigation-grid">
                    <div class="nav-card" onclick="navigateToPage('/engineering-lens')">
                        <span class="nav-icon">🔬</span>
                        <h2>Engineer Lens</h2>
                        <p>Get an engineer's or author's preview into their contribution, throughput, review activity, and code impact</p>
                        <button class="nav-button" onclick="navigateToPage('/engineering-lens')" disabled>View Profile</button>
                    </div>
                    
                    <div class="nav-card" onclick="navigateToPage('/what-shipped')">
                        <span class="nav-icon">📦</span>
                        <h2>What Shipped</h2>
                        <p>Explore recent features, improvements, and changes that have been deployed across your repositories</p>
                        <button class="nav-button" onclick="navigateToPage('/what-shipped')" disabled>Explore</button>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>&copy; 2025 WhatTheRepo. Powered by AI and vector search.</p>
        </div>

        <script>
            let selectedRepo = '';
            
            // Load repositories on page load
            document.addEventListener('DOMContentLoaded', function() {
                loadRepositories();
                loadExampleQueries();
            });
            
            async function loadRepositories() {
                const select = document.getElementById('repo-select');
                
                try {
                    const response = await fetch('/api/repositories');
                    if (!response.ok) {
                        throw new Error('Failed to fetch repositories');
                    }
                    
                    const repos = await response.json();
                    
                    // Clear loading option
                    select.innerHTML = '<option value="">Select a repository</option>';
                    
                    // Add repository options
                    repos.forEach(repo => {
                        const option = document.createElement('option');
                        option.value = repo;
                        option.textContent = repo;
                        select.appendChild(option);
                    });
                    
                    // Add change event listener
                    select.addEventListener('change', onRepoChange);
                    
                } catch (error) {
                    console.error('Error loading repositories:', error);
                    select.innerHTML = '<option value="">Error loading repositories</option>';
                }
            }
            
            function onRepoChange(event) {
                selectedRepo = event.target.value;
                const navigationGrid = document.getElementById('navigation-grid');
                const buttons = document.querySelectorAll('.nav-button');
                const searchSection = document.getElementById('search-section');
                const searchInput = document.getElementById('search-input');
                const searchButton = document.getElementById('search-button');
                
                if (selectedRepo) {
                    // Enable navigation
                    navigationGrid.classList.add('active');
                    buttons.forEach(button => {
                        button.disabled = false;
                    });
                    searchSection.classList.add('active');
                    searchInput.disabled = false;
                    searchButton.disabled = false;
                    loadExampleQueries();
                } else {
                    // Disable navigation
                    navigationGrid.classList.remove('active');
                    buttons.forEach(button => {
                        button.disabled = true;
                    });
                    searchSection.classList.remove('active');
                    searchInput.disabled = true;
                    searchButton.disabled = true;
                }
            }
            
            async function loadExampleQueries() {
                const searchResults = document.getElementById('search-results');
                searchResults.innerHTML = '<p class="loading">Loading example queries...</p>';
                
                try {
                    const response = await fetch(`/api/example-queries?repo=${encodeURIComponent(selectedRepo)}`);
                    if (!response.ok) {
                        throw new Error('Failed to fetch example queries');
                    }
                    const data = await response.json();
                    
                    if (data.queries && data.queries.length > 0) {
                        searchResults.innerHTML = '';
                        data.queries.forEach(query => {
                            const resultItem = document.createElement('div');
                            resultItem.classList.add('result-item');
                            resultItem.innerHTML = `
                                <div class="result-header">
                                    <h3 class="result-title">${query.query}</h3>
                                    <span class="result-meta">${query.type}</span>
                                </div>
                                <p class="result-content">${query.description}</p>
                                <div class="result-tags">
                                    ${query.tags.map(tag => `<span class="result-tag">${tag}</span>`).join('')}
                                </div>
                            `;
                            searchResults.appendChild(resultItem);
                        });
                    } else {
                        searchResults.innerHTML = '<p class="error">No example queries found for this repository.</p>';
                    }
                } catch (error) {
                    console.error('Error loading example queries:', error);
                    searchResults.innerHTML = '<p class="error">Failed to load example queries: ' + error.message + '</p>';
                }
            }

            async function performSearch() {
                const searchInput = document.getElementById('search-input');
                const searchButton = document.getElementById('search-button');
                const searchResults = document.getElementById('search-results');
                const query = searchInput.value.trim();

                if (!selectedRepo) {
                    alert('Please select a repository first');
                    return;
                }

                if (!query) {
                    alert('Please enter a search query');
                    return;
                }

                searchButton.disabled = true;
                searchResults.innerHTML = '<p class="loading">Searching...</p>';

                try {
                    const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&repo_name=${encodeURIComponent(selectedRepo)}&limit=20`);
                    
                    if (!response.ok) {
                        throw new Error('Failed to perform search');
                    }
                    
                    const data = await response.json();
                    
                    if (data.length > 0) {
                        searchResults.innerHTML = '';
                        data.forEach((result, index) => {
                            const resultItem = document.createElement('div');
                            resultItem.classList.add('result-item');
                            
                            const createdDate = new Date(result.created_at * 1000).toLocaleDateString();
                            const mergedDate = result.merged_at ? new Date(result.merged_at * 1000).toLocaleDateString() : 'Not merged';
                            
                            resultItem.innerHTML = `
                                <div class="result-header">
                                    <h3 class="result-title">${result.title}</h3>
                                    <span class="result-meta">PR #${result.pr_number}</span>
                                </div>
                                <p class="result-content">${result.content.substring(0, 300)}${result.content.length > 300 ? '...' : ''}</p>
                                <div class="result-tags">
                                    <span class="result-tag">Author: ${result.author}</span>
                                    <span class="result-tag">Created: ${createdDate}</span>
                                    <span class="result-tag">Merged: ${mergedDate}</span>
                                    <span class="result-tag">Status: ${result.status}</span>
                                    <span class="result-tag">Risk: ${result.risk_band} (${result.risk_score.toFixed(1)})</span>
                                    ${result.feature ? `<span class="result-tag">Feature: ${result.feature}</span>` : ''}
                                </div>
                            `;
                            searchResults.appendChild(resultItem);
                        });
                    } else {
                        searchResults.innerHTML = '<p class="error">No results found for your query.</p>';
                    }
                } catch (error) {
                    console.error('Error performing search:', error);
                    searchResults.innerHTML = '<p class="error">Search failed: ' + error.message + '</p>';
                } finally {
                    searchButton.disabled = false;
                }
            }

            document.getElementById('search-input').addEventListener('keypress', function(event) {
                if (event.key === 'Enter') {
                    event.preventDefault();
                    performSearch();
                }
            });

            document.getElementById('search-button').addEventListener('click', performSearch);
            
            function navigateToPage(page) {
                if (!selectedRepo) {
                    alert('Please select a repository first');
                    return;
                }
                window.location.href = `${page}?repo=${encodeURIComponent(selectedRepo)}`;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/repositories")
async def get_repositories():
    """Get list of available repositories"""
    global milvus_collection
    
    if not milvus_collection:
        print("❌ Repositories endpoint: Milvus collection not initialized")
        # Return empty list instead of raising error for Vercel compatibility
        return []
    
    try:
        print(f"🔍 Repositories endpoint: Querying collection for repo names...")
        
        # Query for distinct repo names
        results = milvus_collection.query(
            expr="",
            output_fields=["repo_name"],
            limit=1000
        )
        
        print(f"📊 Repositories endpoint: Found {len(results)} total records")
        
        # Extract unique repo names
        repo_names = list(set(result['repo_name'] for result in results if result.get('repo_name')))
        repo_names.sort()
        
        print(f"✅ Repositories endpoint: Returning {len(repo_names)} unique repositories")
        return repo_names
        
    except Exception as e:
        print(f"❌ Repositories endpoint: Error fetching repositories: {e}")
        # Return empty list instead of raising error for Vercel compatibility
        return []

@app.get("/api/example-queries")
async def get_example_queries(repo: str = Query(None, description="Selected repository")):
    """Get example queries for a specific repository"""
    if not repo:
        return {"queries": []}

    try:
        # Return generic example queries
        example_queries = [
            {"query": f"What was shipped in {repo} last week?", "type": "Time-based", "description": f"Find PRs shipped in {repo} last 7 days.", "tags": ["time", "last_week", repo]},
            {"query": f"Find PRs by author John Doe in {repo}", "type": "Author-based", "description": f"Search for PRs authored by a specific user in {repo}.", "tags": ["author", "john_doe", repo]},
            {"query": f"What are the top 5 riskiest PRs in {repo}?", "type": "Risk-based", "description": f"Identify PRs with the highest risk scores in {repo}.", "tags": ["risk", "top_risk", repo]},
            {"query": f"Show me all merged PRs from last month in {repo}", "type": "Status-based", "description": f"List all merged PRs from the last 30 days in {repo}.", "tags": ["status", "merged", "last_month", repo]},
            {"query": f"What are the most recent PRs in {repo}?", "type": "Recent-based", "description": f"Find the latest PRs in {repo}.", "tags": ["recent", "latest", repo]}
        ]

        return {"queries": example_queries}
    except Exception as e:
        print(f"Error fetching example queries: {e}")
        return {"queries": []}

@app.get("/api/search")
async def search_prs_get(
    query: str = Query(..., description="Search query"),
    repo_name: str = Query(None, description="Repository name"),
    limit: int = Query(10, description="Number of results to return")
):
    """Search PRs using GET request (for frontend compatibility)"""
    if not milvus_collection:
        return []
    
    try:
        print(f"🔍 Search request: query='{query}', repo='{repo_name}', limit={limit}")
        
        # Generate embedding for the query
        try:
            query_embedding = get_embedding(query)
            print(f"✅ Generated embedding with {len(query_embedding)} dimensions")
        except Exception as embed_error:
            print(f"❌ Embedding generation failed: {embed_error}")
            return []
        
        # Search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"n_top": limit}
        }
        
        # Build search expression
        expr = None
        if repo_name:
            expr = f'repo_name == "{repo_name}"'
        
        print(f"🔍 Performing Milvus vector search with params: {search_params}")
        
        # Perform vector search
        try:
            results = milvus_collection.search(
                data=[query_embedding],
                anns_field="vector",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["pr_id", "pr_number", "title", "body", "author_name", "created_at", "merged_at", "status", "repo_name", "is_merged", "is_closed", "feature", "pr_summary", "risk_score", "risk_band", "risk_reasons", "additions", "deletions", "changed_files"]
            )
            print(f"✅ Milvus search completed, found {len(results)} result sets")
            
        except Exception as search_error:
            print(f"❌ Milvus search failed: {search_error}")
            return []
        
        search_results = []
        seen_pr_ids = set()
        
        try:
            for hits in results:
                for hit in hits:
                    hit_data = hit.fields if hasattr(hit, 'fields') else {}
                    pr_id = hit_data.get('pr_id', 0)
                    
                    if pr_id in seen_pr_ids:
                        continue
                    
                    seen_pr_ids.add(pr_id)
                    
                    # Convert any numpy types safely
                    pr_id = convert_numpy_types_safe(pr_id)
                    pr_number = convert_numpy_types_safe(hit_data.get('pr_number', 0))
                    title = convert_numpy_types_safe(hit_data.get('title', '')) or ''
                    body = convert_numpy_types_safe(hit_data.get('body', '')) or ''
                    author_name = convert_numpy_types_safe(hit_data.get('author_name', '')) or ''
                    created_at = convert_numpy_types_safe(hit_data.get('created_at', 0)) or 0
                    merged_at = convert_numpy_types_safe(hit_data.get('merged_at', 0)) or 0
                    status = convert_numpy_types_safe(hit_data.get('status', '')) or ''
                    is_merged = convert_numpy_types_safe(hit_data.get('is_merged', False)) or False
                    is_closed = convert_numpy_types_safe(hit_data.get('is_closed', False)) or False
                    feature = convert_numpy_types_safe(hit_data.get('feature', '')) or ''
                    pr_summary = convert_numpy_types_safe(hit_data.get('pr_summary', '')) or ''
                    risk_score = convert_numpy_types_safe(hit_data.get('risk_score', 0.0)) or 0.0
                    risk_band = convert_numpy_types_safe(hit_data.get('risk_band', 'low')) or 'low'
                    risk_reasons = convert_numpy_types_safe(hit_data.get('risk_reasons', [])) or []
                    additions = convert_numpy_types_safe(hit_data.get('additions', 0)) or 0
                    deletions = convert_numpy_types_safe(hit_data.get('deletions', 0)) or 0
                    changed_files = convert_numpy_types_safe(hit_data.get('changed_files', 0)) or 0
                    
                    search_results.append(SearchResult(
                        pr_id=pr_id,
                        pr_number=pr_number,
                        title=title,
                        content=body,
                        text_type="pr_data",
                        file_path="",
                        function_name="",
                        similarity_score=hit.score,
                        author=author_name,
                        created_at=created_at,
                        merged_at=merged_at,
                        status=status,
                        is_merged=is_merged,
                        is_closed=is_closed,
                        feature=feature,
                        pr_summary=pr_summary,
                        risk_score=risk_score,
                        risk_band=risk_band,
                        risk_reasons=risk_reasons,
                        additions=additions,
                        deletions=deletions,
                        changed_files=changed_files,
                        file_details=[]
                    ))
            
            print(f"✅ Processed {len(search_results)} search results")
            return search_results
            
        except Exception as process_error:
            print(f"❌ Error processing search results: {process_error}")
            return []
            
    except Exception as e:
        print(f"Error performing search: {e}")
        return []

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "milvus_connected": milvus_collection is not None,
        "openai_connected": openai_client is not None,
        "deployment": "vercel"
    }

# Vercel serverless function handler
def handler(request, context):
    """Vercel serverless function handler"""
    return app(request, context)
