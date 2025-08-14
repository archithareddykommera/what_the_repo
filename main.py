#!/usr/bin/env python3
"""
FastAPI application for GitHub PR summarization and Q&A using Milvus vector database.
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
import uvicorn
from pymilvus import connections, Collection, utility
import openai
from openai import OpenAI
from supabase import create_client, Client

def create_supabase_client():
    """Create Supabase client with proxy environment variables cleared"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not supabase_url or not supabase_key:
        raise ValueError("Supabase configuration not found")
    
    # Clear any proxy environment variables that might interfere
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy']
    for var in proxy_vars:
        if var in os.environ:
            del os.environ[var]
    
    return create_client(supabase_url, supabase_key)
import logging

app = FastAPI(title="What the repo-gpt", description="GitHub PR analysis and insights")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables
milvus_collection = None
openai_client = None
embedding_dim = 1536  # Match your collection dimension
engineer_lens_ui = None

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global milvus_collection, openai_client, engineer_lens_ui
    try:
        initialize_connections()
        # Initialize Engineer Lens UI
        engineer_lens_ui = EngineerLensUI()
        print("✅ FastAPI startup: Connections initialized successfully")
    except Exception as e:
        print(f"❌ FastAPI startup: Failed to initialize connections: {e}")
        # Don't raise here, let the app start but endpoints will handle the error

class SearchRequest(BaseModel):
    query: str
    repo_name: Optional[str] = None
    limit: int = 5

class PRTimeline(BaseModel):
    pr_id: int
    pr_number: int
    title: str
    created_at: int
    status: str
    author: str
    is_merged: bool
    is_closed: bool

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

class EngineerLensUI:
    def __init__(self):
        """Initialize Supabase connection"""
        self.supabase_client = None
        self._init_supabase()
    
    def _init_supabase(self):
        """Initialize Supabase connection"""
        try:
            self.supabase_client = create_supabase_client()
            print("✅ Connected to Supabase for Engineer Lens UI")
            
        except Exception as e:
            print(f"❌ Failed to initialize Supabase: {e}")
            raise
    
    def get_engineers_for_repo(self, repo_name: str) -> List[Dict]:
        """Get list of engineers who have contributed to a repository"""
        try:
            # Get unique authors from the authors table
            response = self.supabase_client.table('authors').select('*').execute()
            authors = response.data
            
            # Filter authors who have metrics for this repo
            repo_authors = []
            for author in authors:
                # Check if author has any metrics for this repo
                metrics_response = self.supabase_client.table('author_metrics_window').select('username').eq('repo_name', repo_name).eq('username', author['username']).limit(1).execute()
                if metrics_response.data:
                    repo_authors.append(author)
            
            print(f"📊 Found {len(repo_authors)} engineers for {repo_name}")
            return repo_authors
            
        except Exception as e:
            print(f"❌ Error fetching engineers for {repo_name}: {e}")
            return []
    
    def get_engineer_metrics(self, username: str, repo_name: str, window_days: int = 30) -> Dict:
        """Get comprehensive metrics for a specific engineer"""
        try:
            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=window_days)
            
            # Get window metrics
            metrics_response = self.supabase_client.table('author_metrics_window').select('*').eq('username', username).eq('repo_name', repo_name).eq('window_days', window_days).eq('end_date', end_date.isoformat()).execute()
            
            if not metrics_response.data:
                # Return empty metrics if no data found
                return {
                    'username': username,
                    'repo_name': repo_name,
                    'window_days': window_days,
                    'prs_submitted': 0,
                    'prs_merged': 0,
                    'high_risk_prs': 0,
                    'high_risk_rate': 0.0,
                    'lines_changed': 0,
                    'ownership_low_risk_prs': 0
                }
            
            metrics = metrics_response.data[0]
            
            # Get file ownership data
            ownership_response = self.supabase_client.table('author_file_ownership').select('*').eq('username', username).eq('repo_name', repo_name).eq('window_days', window_days).eq('end_date', end_date.isoformat()).order('ownership_pct', desc=True).limit(10).execute()
            
            # Get PR features data
            features_response = self.supabase_client.table('author_prs_window').select('*').eq('username', username).eq('repo_name', repo_name).eq('window_days', window_days).eq('end_date', end_date.isoformat()).order('merged_at', desc=True).limit(10).execute()
            
            return {
                'username': username,
                'repo_name': repo_name,
                'window_days': window_days,
                'prs_submitted': metrics.get('prs_submitted', 0),
                'prs_merged': metrics.get('prs_merged', 0),
                'high_risk_prs': metrics.get('high_risk_prs', 0),
                'high_risk_rate': metrics.get('high_risk_rate', 0.0),
                'lines_changed': metrics.get('lines_changed', 0),
                'ownership_low_risk_prs': metrics.get('ownership_low_risk_prs', 0),
                'file_ownership': ownership_response.data,
                'features': features_response.data
            }
            
        except Exception as e:
            print(f"❌ Error fetching metrics for {username} in {repo_name}: {e}")
            return {}
    
    def get_engineer_lens_html(self, repo_name: str) -> str:
        """Generate the Engineer Lens HTML page"""
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Engineer Lens - What the repo</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                    color: #ffffff;
                    min-height: 100vh;
                }}
                
                .header {{
                    background: rgba(0, 0, 0, 0.3);
                    backdrop-filter: blur(10px);
                    padding: 1.5rem 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                }}
                
                .nav-container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 0 2rem;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                
                .logo {{
                    font-size: 1.5rem;
                    font-weight: 700;
                    color: #00d4ff;
                    text-decoration: none;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                }}
                
                .back-button {{
                    background: rgba(255, 255, 255, 0.1);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    padding: 8px 16px;
                    border-radius: 20px;
                    text-decoration: none;
                    transition: all 0.3s ease;
                }}
                
                .back-button:hover {{
                    background: rgba(255, 255, 255, 0.2);
                }}
                
                .main-content {{
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 3rem 2rem;
                }}
                
                .page-title {{
                    text-align: center;
                    margin-bottom: 3rem;
                }}
                
                .page-title h1 {{
                    font-size: 3rem;
                    margin-bottom: 1rem;
                    background: linear-gradient(45deg, #00d4ff, #4ecdc4);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }}
                
                .page-title p {{
                    font-size: 1.2rem;
                    color: #b0b0b0;
                    margin-bottom: 1rem;
                }}
                
                .repo-info {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    padding: 1.5rem;
                    margin-bottom: 2rem;
                    text-align: center;
                    backdrop-filter: blur(10px);
                }}
                
                .repo-info h3 {{
                    color: #00d4ff;
                    font-size: 1.3rem;
                    margin-bottom: 0.5rem;
                }}
                
                .repo-info p {{
                    color: #b0b0b0;
                    font-size: 1rem;
                }}
                
                .engineer-selector {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    padding: 2rem;
                    margin-bottom: 2rem;
                    text-align: center;
                    backdrop-filter: blur(10px);
                }}
                
                .engineer-selector h2 {{
                    font-size: 1.8rem;
                    margin-bottom: 1rem;
                    color: #ffffff;
                }}
                
                .engineer-selector p {{
                    color: #b0b0b0;
                    margin-bottom: 1.5rem;
                }}
                
                .select-container {{
                    display: flex;
                    gap: 1rem;
                    justify-content: center;
                    align-items: center;
                    flex-wrap: wrap;
                }}
                
                .engineer-select {{
                    padding: 12px 20px;
                    background: rgba(255, 255, 255, 0.1);
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                    color: #ffffff;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    backdrop-filter: blur(10px);
                    min-width: 200px;
                }}
                
                .engineer-select:focus {{
                    outline: none;
                    border-color: #00d4ff;
                    box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
                }}
                
                .time-select {{
                    padding: 12px 20px;
                    background: rgba(255, 255, 255, 0.1);
                    border: 2px solid rgba(255, 255, 255, 0.2);
                    border-radius: 10px;
                    color: #ffffff;
                    font-size: 1rem;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    backdrop-filter: blur(10px);
                }}
                
                .time-select:focus {{
                    outline: none;
                    border-color: #00d4ff;
                    box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
                }}
                
                .engineer-select option {{
                    background: #1a1a2e;
                    color: #ffffff;
                    padding: 8px 12px;
                }}
                
                .time-select option {{
                    background: #1a1a2e;
                    color: #ffffff;
                    padding: 8px 12px;
                }}
                
                .engineer-dashboard {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    padding: 2rem;
                    backdrop-filter: blur(10px);
                    display: none;
                }}
                
                .dashboard-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 2rem;
                    flex-wrap: wrap;
                    gap: 1rem;
                }}
                
                .engineer-profile {{
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                }}
                
                .profile-avatar {{
                    width: 60px;
                    height: 60px;
                    border-radius: 50%;
                    background: linear-gradient(45deg, #00d4ff, #4ecdc4);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 1.5rem;
                    font-weight: bold;
                }}
                
                .profile-info h2 {{
                    font-size: 1.8rem;
                    margin-bottom: 0.5rem;
                    color: #ffffff;
                }}
                
                .profile-info p {{
                    color: #b0b0b0;
                    font-size: 1rem;
                }}
                
                .time-filter {{
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                }}
                
                .metrics-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 2rem;
                    margin-bottom: 3rem;
                }}
                
                .metric-card {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    padding: 2rem;
                    backdrop-filter: blur(10px);
                    transition: all 0.3s ease;
                }}
                
                .metric-card:hover {{
                    border-color: rgba(255, 255, 255, 0.2);
                    transform: translateY(-5px);
                }}
                
                .metric-card h3 {{
                    font-size: 1.3rem;
                    margin-bottom: 1.5rem;
                    color: #00d4ff;
                    text-align: center;
                }}
                
                .metric-content {{
                    display: flex;
                    flex-direction: column;
                    gap: 1.5rem;
                }}
                
                .metric-item {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 10px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }}
                
                .metric-value {{
                    font-size: 2rem;
                    font-weight: bold;
                    color: #4ecdc4;
                }}
                
                .metric-label {{
                    font-size: 1rem;
                    color: #b0b0b0;
                    text-align: right;
                }}
                
                .dashboard-sections {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                    gap: 2rem;
                }}
                
                .section-card {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 15px;
                    padding: 2rem;
                    backdrop-filter: blur(10px);
                }}
                
                .section-card h3 {{
                    font-size: 1.5rem;
                    margin-bottom: 1.5rem;
                    color: #00d4ff;
                }}
                
                .heatmap-content {{
                    max-height: 400px;
                    overflow-y: auto;
                }}
                
                .ownership-item {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1rem;
                    margin-bottom: 0.5rem;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 8px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }}
                
                .file-path {{
                    font-size: 0.9rem;
                    color: #ffffff;
                    flex: 1;
                    margin-right: 1rem;
                    font-weight: 500;
                }}
                
                .ownership-pct {{
                    font-size: 1.1rem;
                    font-weight: bold;
                    color: #ffffff;
                    min-width: 60px;
                    text-align: right;
                    position: absolute;
                    right: 8px;
                    top: 50%;
                    transform: translateY(-50%);
                    z-index: 2;
                    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
                }}
                
                .ownership-bar-container {{
                    position: relative;
                    width: 120px;
                    height: 24px;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    overflow: hidden;
                }}
                
                .ownership-bar {{
                    height: 100%;
                    border-radius: 12px;
                    transition: all 0.3s ease;
                    position: relative;
                }}
                
                .features-content {{
                    max-height: 400px;
                    overflow-y: auto;
                }}
                
                .feature-item {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 10px;
                    padding: 1.5rem;
                    margin-bottom: 1rem;
                    transition: all 0.3s ease;
                }}
                
                .feature-item:hover {{
                    border-color: rgba(255, 255, 255, 0.2);
                    transform: translateY(-2px);
                }}
                
                .feature-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 1rem;
                }}
                
                .feature-title {{
                    font-size: 1.1rem;
                    font-weight: 600;
                    color: #ffffff;
                    flex: 1;
                    margin-right: 1rem;
                }}
                
                .feature-meta {{
                    font-size: 0.9rem;
                    color: #b0b0b0;
                    text-align: right;
                }}
                
                .feature-description {{
                    color: #e0e0e0;
                    line-height: 1.6;
                    margin-bottom: 1rem;
                }}
                
                .feature-tags {{
                    display: flex;
                    gap: 0.5rem;
                    flex-wrap: wrap;
                }}
                
                .feature-tag {{
                    background: rgba(0, 212, 255, 0.2);
                    color: #00d4ff;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    border: 1px solid rgba(0, 212, 255, 0.3);
                }}
                
                .loading {{
                    text-align: center;
                    color: #00d4ff;
                    font-style: italic;
                    padding: 2rem;
                }}
                
                .error {{
                    text-align: center;
                    color: #ff6b6b;
                    font-style: italic;
                    padding: 2rem;
                }}
                
                .placeholder-content {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                    padding: 3rem;
                    text-align: center;
                    backdrop-filter: blur(10px);
                }}
                
                .placeholder-icon {{
                    font-size: 4rem;
                    margin-bottom: 2rem;
                    opacity: 0.7;
                }}
                
                .placeholder-text {{
                    font-size: 1.2rem;
                    color: #b0b0b0;
                    line-height: 1.6;
                }}
                
                @media (max-width: 768px) {{
                    .dashboard-header {{
                        flex-direction: column;
                        align-items: flex-start;
                    }}
                    
                    .metrics-grid {{
                        grid-template-columns: 1fr;
                    }}
                    
                    .dashboard-sections {{
                        grid-template-columns: 1fr;
                    }}
                    
                    .select-container {{
                        flex-direction: column;
                        align-items: stretch;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="nav-container">
                    <a href="/" class="logo">🔍 What the repo</a>
                    <a href="/" class="back-button">← Back to Home</a>
                </div>
            </div>
            
            <div class="main-content">
                <div class="page-title">
                    <h1>Engineer Lens</h1>
                    <p>Get an engineer's preview into their contribution, throughput, and code impact</p>
                    <div class="repo-info">
                        <h3>Selected Repository</h3>
                        <p>{repo_name}</p>
                    </div>
                </div>
                
                <div class="engineer-selector">
                    <h2>Select Engineer</h2>
                    <p>Choose an engineer to view their contribution metrics and insights</p>
                    <div class="select-container">
                        <select id="engineer-select" class="engineer-select">
                            <option value="">Loading engineers...</option>
                        </select>
                        <select id="time-filter" class="time-select">
                            <option value="30">Last 30 days</option>
                            <option value="90">Last 90 days</option>
                            <option value="180">Last 6 months</option>
                            <option value="365">Last year</option>
                        </select>
                    </div>
                </div>
                
                <div class="engineer-dashboard" id="engineer-dashboard">
                    <div class="dashboard-header">
                        <div class="engineer-profile">
                            <div class="profile-avatar" id="profile-avatar">👤</div>
                            <div class="profile-info">
                                <h2 id="engineer-name">Engineer Name</h2>
                                <p id="engineer-repo">{repo_name}</p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <h3>Throughput</h3>
                            <div class="metric-content">
                                <div class="metric-item">
                                    <span class="metric-value" id="prs-submitted">0</span>
                                    <span class="metric-label">PRs Submitted</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-value" id="prs-merged">0</span>
                                    <span class="metric-label">PRs Merged</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="metric-card">
                            <h3>Risk Assessment</h3>
                            <div class="metric-content">
                                <div class="metric-item">
                                    <span class="metric-value" id="high-risk-prs">0%</span>
                                    <span class="metric-label">High-Risk PRs</span>
                                </div>
                                <div class="metric-item">
                                    <span class="metric-value" id="avg-risk-score">0.0</span>
                                    <span class="metric-label">Avg Risk Score</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="dashboard-sections">
                        <div class="section-card">
                            <h3>Contribution Heatmap</h3>
                            <div id="contribution-heatmap" class="heatmap-content">
                                <p class="loading">Loading contribution data...</p>
                            </div>
                        </div>
                        
                        <div class="section-card">
                            <h3>Features Added</h3>
                            <div id="features-added" class="features-content">
                                <p class="loading">Loading features data...</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="placeholder-content" id="placeholder-content">
                    <div class="placeholder-icon">👤</div>
                    <div class="placeholder-text">
                        <p>Select an engineer from the dropdown above to view their detailed contribution metrics and insights.</p>
                        <p>This will show:</p>
                        <ul style="text-align: left; max-width: 600px; margin: 1rem auto;">
                            <li>Throughput metrics (PRs submitted, merged)</li>
                            <li>Contribution heatmap by file/component</li>
                            <li>Features added and their impact</li>
                            <li>Risk assessment of contributions</li>
                        </ul>
                        <p><strong>Repository:</strong> {repo_name}</p>
                    </div>
                </div>
            </div>

            <script>
                const repoName = '{repo_name}';
                let selectedEngineer = '';
                let selectedTimeWindow = 30;
                
                // Load engineers on page load
                document.addEventListener('DOMContentLoaded', function() {{
                    loadEngineers();
                }});
                
                async function loadEngineers() {{
                    const select = document.getElementById('engineer-select');
                    
                    try {{
                        const response = await fetch(`/api/engineers?repo=${{encodeURIComponent(repoName)}}`);
                        if (!response.ok) {{
                            throw new Error('Failed to fetch engineers');
                        }}
                        
                        const engineers = await response.json();
                        
                        // Clear loading option
                        select.innerHTML = '<option value="">Select an engineer</option>';
                        
                        // Add engineer options
                        engineers.forEach(engineer => {{
                            const option = document.createElement('option');
                            option.value = engineer.username;
                            option.textContent = engineer.display_name || engineer.username;
                            select.appendChild(option);
                        }});
                        
                        // Add change event listener
                        select.addEventListener('change', onEngineerChange);
                        
                    }} catch (error) {{
                        console.error('Error loading engineers:', error);
                        select.innerHTML = '<option value="">Error loading engineers</option>';
                    }}
                }}
                
                function onEngineerChange(event) {{
                    selectedEngineer = event.target.value;
                    const dashboard = document.getElementById('engineer-dashboard');
                    const placeholder = document.getElementById('placeholder-content');
                    
                    if (selectedEngineer) {{
                        dashboard.style.display = 'block';
                        placeholder.style.display = 'none';
                        loadEngineerData();
                    }} else {{
                        dashboard.style.display = 'none';
                        placeholder.style.display = 'block';
                    }}
                }}
                
                // Add time filter change listener
                document.getElementById('time-filter').addEventListener('change', function(event) {{
                    selectedTimeWindow = parseInt(event.target.value);
                    if (selectedEngineer) {{
                        loadEngineerData();
                    }}
                }});
                
                async function loadEngineerData() {{
                    if (!selectedEngineer) return;
                    
                    try {{
                        const response = await fetch(`/api/engineer-metrics?username=${{encodeURIComponent(selectedEngineer)}}&repo=${{encodeURIComponent(repoName)}}&window_days=${{selectedTimeWindow}}`);
                        if (!response.ok) {{
                            throw new Error('Failed to fetch engineer data');
                        }}
                        
                        const data = await response.json();
                        displayEngineerData(data);
                        
                    }} catch (error) {{
                        console.error('Error loading engineer data:', error);
                        document.getElementById('engineer-dashboard').innerHTML = '<div class="error">Failed to load engineer data: ' + error.message + '</div>';
                    }}
                }}
                
                function displayEngineerData(data) {{
                    // Update profile
                    document.getElementById('engineer-name').textContent = data.username;
                    document.getElementById('profile-avatar').textContent = data.username.charAt(0).toUpperCase();
                    
                    // Update metrics
                    document.getElementById('prs-submitted').textContent = data.prs_submitted || 0;
                    document.getElementById('prs-merged').textContent = data.prs_merged || 0;
                    document.getElementById('high-risk-prs').textContent = (data.high_risk_rate || 0).toFixed(1) + '%';
                    document.getElementById('avg-risk-score').textContent = (data.avg_risk_score || 0).toFixed(1);
                    
                    // Update contribution heatmap
                    const heatmapContainer = document.getElementById('contribution-heatmap');
                    if (data.file_ownership && data.file_ownership.length > 0) {{
                        console.log('File ownership data:', data.file_ownership);
                        heatmapContainer.innerHTML = data.file_ownership.map(ownership => {{
                            const percentage = ownership.ownership_pct;
                            const intensity = Math.min(percentage / 100, 1);
                            const color = `rgba(0, 212, 255, ${{intensity * 0.8 + 0.2}})`;
                            const filePath = ownership.file_path || ownership.file_id || 'Unknown file';
                            
                            return `
                                <div class="ownership-item">
                                    <div class="file-path">${{filePath}}</div>
                                    <div class="ownership-bar-container">
                                        <div class="ownership-bar" style="width: ${{percentage}}%; background: ${{color}};"></div>
                                        <div class="ownership-pct">${{percentage}}%</div>
                                    </div>
                                </div>
                            `;
                        }}).join('');
                    }} else {{
                        heatmapContainer.innerHTML = '<p class="loading">No file ownership data available</p>';
                    }}
                    
                    // Update features added
                    const featuresContainer = document.getElementById('features-added');
                    if (data.features && data.features.length > 0) {{
                        featuresContainer.innerHTML = data.features.map(feature => {{
                            const mergedDate = new Date(feature.merged_at).toLocaleDateString();
                            const riskClass = feature.high_risk ? 'high-risk' : feature.risk_score > 5 ? 'medium-risk' : 'low-risk';
                            
                            return `
                                <div class="feature-item">
                                    <div class="feature-header">
                                        <div class="feature-title">${{feature.title}}</div>
                                        <div class="feature-meta">PR #${{feature.pr_number}}</div>
                                    </div>
                                    ${{feature.pr_summary ? `<div class="feature-description">${{feature.pr_summary}}</div>` : ''}}
                                    <div class="feature-tags">
                                        <span class="feature-tag">Risk: ${{feature.risk_score.toFixed(1)}}/10</span>
                                        <span class="feature-tag">${{feature.high_risk ? 'High Risk' : 'Low Risk'}}</span>
                                        <span class="feature-tag">Merged: ${{mergedDate}}</span>
                                        ${{feature.feature_confidence > 0.5 ? `<span class="feature-tag">Feature (${{(feature.feature_confidence * 100).toFixed(0)}}% confidence)</span>` : ''}}
                                    </div>
                                </div>
                            `;
                        }}).join('');
                    }} else {{
                        featuresContainer.innerHTML = '<p class="loading">No features data available</p>';
                    }}
                }}
            </script>
        </body>
        </html>
        """

def initialize_connections():
    """Initialize Milvus and OpenAI connections"""
    global milvus_collection, openai_client, embedding_dim
    
    # Initialize Milvus connection
    milvus_url = os.getenv('MILVUS_URL')
    milvus_token = os.getenv('MILVUS_TOKEN')
    collection_name = os.getenv('COLLECTION_NAME', 'pr_index_what_the_repo')
    
    if not milvus_url or not milvus_token:
        raise ValueError("MILVUS_URL and MILVUS_TOKEN environment variables are required")
    
    try:
        connections.connect(
            alias="default",
            uri=milvus_url,
            token=milvus_token
        )
        
        if not utility.has_collection(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")
        
        milvus_collection = Collection(collection_name)
        milvus_collection.load()
        
        # Get actual dimension from collection schema
        schema = milvus_collection.schema
        for field in schema.fields:
            if field.name == "vector":
                embedding_dim = field.params.get('dim', 1536)
                break
        
        print(f"Connected to Milvus collection '{collection_name}' with dimension {embedding_dim}")
        
    except Exception as e:
        print(f"Failed to connect to Milvus: {e}")
        raise
    
    # Initialize OpenAI client
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        print("OpenAI client initialized successfully")
    except Exception as e:
        print(f"Failed to initialize OpenAI client: {e}")
        raise

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

@app.get("/", response_class=HTMLResponse)
async def home_page():
    """Home page with dark mode UI and repo selector"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>What the repo</title>
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
            
            .repo-selector p {
                color: #b0b0b0;
                margin-bottom: 1rem;
                line-height: 1.4;
                font-size: 0.9rem;
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
            
            .repo-select option {
                background: #1a1a2e;
                color: #ffffff;
                padding: 10px;
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
            
            .search-results {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 2rem;
                margin-top: 2rem;
                text-align: left;
                backdrop-filter: blur(10px);
                max-height: 500px;
                overflow-y: auto;
                display: block;
            }
            
            .search-results.hidden {
                display: none;
            }
            
            .result-item {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 1.5rem;
                margin-bottom: 1rem;
                transition: all 0.3s ease;
            }
            
            .result-item:hover {
                border-color: rgba(255, 255, 255, 0.2);
                transform: translateY(-2px);
            }
            
            .result-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 1rem;
            }
            
            .result-title {
                font-size: 1.2rem;
                font-weight: 600;
                color: #ffffff;
                margin-bottom: 0.5rem;
            }
            
            .result-meta {
                font-size: 0.9rem;
                color: #b0b0b0;
                margin-bottom: 1rem;
            }
            
            .result-content {
                color: #e0e0e0;
                line-height: 1.6;
                margin-bottom: 1rem;
            }
            
            .result-tags {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
            }
            
                         .result-tag {
                 background: rgba(0, 212, 255, 0.2);
                 color: #00d4ff;
                 padding: 4px 12px;
                 border-radius: 20px;
                 font-size: 0.8rem;
                 border: 1px solid rgba(0, 212, 255, 0.3);
             }
             
                         .pr-summary {
                background: rgba(0, 212, 255, 0.1);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 8px;
                padding: 1rem;
                margin: 1rem 0;
                color: #00d4ff;
                font-size: 0.95rem;
                line-height: 1.5;
            }
            
            .ai-summary {
                background: rgba(76, 175, 80, 0.1);
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 8px;
                padding: 1rem;
                margin: 1rem 0;
                color: #4caf50;
                font-size: 0.95rem;
                line-height: 1.5;
                font-style: italic;
            }
            
            .risk-factors {
                background: rgba(255, 193, 7, 0.1);
                border-left: 4px solid #ffc107;
                border-radius: 8px;
                padding: 1rem;
                margin: 1rem 0;
                color: #ffd54f;
                font-size: 0.9rem;
            }
            
            .risk-factors ul {
                margin: 0.5rem 0 0 0;
                padding-left: 1.5rem;
            }
            
            .risk-factors li {
                margin: 0.25rem 0;
                color: #ffd54f;
            }
            
            .file-details {
                background: rgba(76, 175, 80, 0.1);
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 8px;
                padding: 0.8rem;
                margin: 1rem 0;
                color: #4caf50;
                font-size: 0.9rem;
            }
            
            .result-actions {
                margin-top: 1rem;
                text-align: center;
            }
            
            .view-pr-btn {
                background: linear-gradient(45deg, #00d4ff, #4ecdc4);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-size: 0.9rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .view-pr-btn:hover {
                transform: scale(1.05);
                box-shadow: 0 5px 15px rgba(0, 212, 255, 0.3);
            }
            
            .loading {
                text-align: center;
                color: #00d4ff;
                font-style: italic;
                padding: 2rem;
            }
            
            .error {
                text-align: center;
                color: #ff6b6b;
                font-style: italic;
                padding: 2rem;
            }
            
            .example-queries {
                margin-top: 1rem;
                font-size: 0.9rem;
                color: #b0b0b0;
            }
            
            .example-queries strong {
                color: #00d4ff;
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
            <h1>🔍 What the repo</h1>
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
                </div>
                
        <div class="footer">
            <p>&copy; 2025 What the repo. Powered by AI and vector search.</p>
        </div>

        <script>
            let selectedRepo = '';
            
            // Load repositories on page load
            document.addEventListener('DOMContentLoaded', function() {
                loadRepositories();
                loadExampleQueries(); // Load example queries on page load
            });
            
            async function loadRepositories() {
                const select = document.getElementById('repo-select');
                const statusElement = select.parentElement;
                
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
                    select.classList.add('error');
                }
            }
            
            function onRepoChange(event) {
                selectedRepo = event.target.value;
                const navigationGrid = document.getElementById('navigation-grid');
                const buttons = document.querySelectorAll('.nav-button');
                const searchSection = document.getElementById('search-section');
                const searchInput = document.getElementById('search-input');
                const searchButton = document.getElementById('search-button');
                const searchResults = document.getElementById('search-results');
                
                if (selectedRepo) {
                    // Enable navigation
                    navigationGrid.classList.add('active');
                    buttons.forEach(button => {
                        button.disabled = false;
                    });
                    searchSection.classList.add('active');
                    searchInput.disabled = false;
                    searchButton.disabled = false;
                    searchResults.classList.remove('error', 'hidden');
                    searchResults.innerHTML = ''; // Clear previous results
                    loadExampleQueries(); // Reload example queries for the new repo
                } else {
                    // Disable navigation
                    navigationGrid.classList.remove('active');
                    buttons.forEach(button => {
                        button.disabled = true;
                    });
                    searchSection.classList.remove('active');
                    searchInput.disabled = true;
                    searchButton.disabled = true;
                    searchResults.classList.add('error', 'hidden');
                    searchResults.innerHTML = '<p class="error">Please select a repository to search.</p>';
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
                        searchResults.innerHTML = ''; // Clear loading message
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
                    console.log('🔍 Starting search for:', query);
                    const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&repo_name=${encodeURIComponent(selectedRepo)}&limit=20`);
                    console.log('🔍 Search response status:', response.status);
                    
                    if (!response.ok) {
                        throw new Error('Failed to perform search');
                    }
                    
                    const data = await response.json();
                    console.log('🔍 Search results data:', data);
                    console.log('🔍 Number of results:', data.length);
                    
                    if (data.length > 0) {
                        searchResults.innerHTML = ''; // Clear loading message
                        searchResults.classList.remove('hidden'); // Make sure results are visible
                        console.log('🔍 Rendering', data.length, 'results');
                        data.forEach((result, index) => {
                            console.log('🔍 Rendering result', index + 1, ':', result);
                            const resultItem = document.createElement('div');
                            resultItem.classList.add('result-item');
                            
                            // Format dates
                            const createdDate = new Date(result.created_at * 1000).toLocaleDateString();
                            const mergedDate = result.merged_at ? new Date(result.merged_at * 1000).toLocaleDateString() : 'Not merged';
                            
                            // Create PR summary
                            const summaryParts = [];
                            if (result.feature) {
                                summaryParts.push(`<strong>Feature:</strong> ${result.feature}`);
                            }
                            summaryParts.push(`<strong>Risk Level:</strong> ${result.risk_band.toUpperCase()} (${result.risk_score.toFixed(1)}/10)`);
                            summaryParts.push(`<strong>Changes:</strong> +${result.additions} -${result.deletions} across ${result.changed_files} files`);
                            summaryParts.push(`<strong>Status:</strong> ${result.is_merged ? 'Merged' : result.is_closed ? 'Closed' : 'Open'}`);
                            
                            const summaryHtml = `<div class="pr-summary">${summaryParts.join(' • ')}</div>`;
                            
                            // Add PR summary if available
                            const aiSummaryHtml = result.pr_summary && result.pr_summary.trim() 
                                ? `<div class="ai-summary"><strong>PR Summary:</strong> ${result.pr_summary}</div>` 
                                : '';
                            
                            // Format risk factors (changed from risk reasons)
                            const riskFactorsHtml = result.risk_reasons && result.risk_reasons.length > 0 
                                ? `<div class="risk-factors"><strong>Risk Factors:</strong><ul>${result.risk_reasons.map(reason => `<li>${reason}</li>`).join('')}</ul></div>` 
                                : '';
                            
                            // Format file details if available
                            const fileDetailsHtml = result.file_details && result.file_details.length > 0 
                                ? `<div class="file-details"><strong>Files Changed:</strong> ${result.file_details.length} files</div>` 
                                : '';
                            
                            resultItem.innerHTML = `
                                <div class="result-header">
                                    <h3 class="result-title">${result.title}</h3>
                                    <span class="result-meta">PR #${result.pr_number}</span>
                                </div>
                                ${summaryHtml}
                                ${aiSummaryHtml}
                                <p class="result-content">${result.content.substring(0, 300)}${result.content.length > 300 ? '...' : ''}</p>
                                <div class="result-tags">
                                    <span class="result-tag">Author: ${result.author}</span>
                                    <span class="result-tag">Created: ${createdDate}</span>
                                    <span class="result-tag">Merged: ${mergedDate}</span>
                                    <span class="result-tag">Status: ${result.status}</span>
                                    <span class="result-tag">Risk: ${result.risk_band} (${result.risk_score.toFixed(1)})</span>
                                    ${result.feature ? `<span class="result-tag">Feature: ${result.feature}</span>` : ''}
                                    <span class="result-tag">Changes: +${result.additions} -${result.deletions} (${result.changed_files} files)</span>
                                </div>
                                ${riskFactorsHtml}
                                ${fileDetailsHtml}
                                <div class="result-actions">
                                    <button class="view-pr-btn" onclick="viewPRDetails(${result.pr_id}, '${result.repo_name || ''}')">View Full PR Details</button>
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

                // Navigate to page with repo parameter
                window.location.href = `${page}?repo=${encodeURIComponent(selectedRepo)}`;
            }
            
            function viewPRDetails(prId, repoName) {
                if (!repoName) {
                    repoName = selectedRepo;
                }
                if (!repoName) {
                    alert('Please select a repository first');
                    return;
                }
                
                // Navigate to PR details page
                window.location.href = `/pr-details?pr_id=${prId}&repo=${encodeURIComponent(repoName)}`;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/test-milvus")
async def test_milvus():
    """Test Milvus connection and collection status"""
    global milvus_collection
    
    try:
        # Check if collection is initialized
        if not milvus_collection:
            return {
                "status": "error",
                "message": "Milvus collection not initialized",
                "collection_name": os.getenv('COLLECTION_NAME', 'pr_index_what_the_repo'),
                "milvus_url": os.getenv('MILVUS_URL', 'not_set'),
                "has_token": bool(os.getenv('MILVUS_TOKEN'))
            }
        
        # Try to get collection info
        collection_name = milvus_collection.name
        schema = milvus_collection.schema
        field_names = [field.name for field in schema.fields]
        
        # Try a simple query
        try:
            test_results = milvus_collection.query(
                expr="",
                output_fields=["repo_name"],
                limit=1
            )
            query_success = True
            record_count = len(test_results) if test_results else 0
        except Exception as query_error:
            query_success = False
            record_count = 0
            query_error_msg = str(query_error)
        
        return {
            "status": "success" if query_success else "partial",
            "collection_name": collection_name,
            "field_names": field_names,
            "query_success": query_success,
            "record_count": record_count,
            "query_error": query_error_msg if not query_success else None
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error testing Milvus: {str(e)}",
            "collection_name": os.getenv('COLLECTION_NAME', 'pr_index_what_the_repo'),
            "milvus_url": os.getenv('MILVUS_URL', 'not_set'),
            "has_token": bool(os.getenv('MILVUS_TOKEN'))
        }

@app.get("/api/test-search")
async def test_search():
    """Test search functionality with a simple query"""
    if not milvus_collection:
        return {"status": "error", "message": "Milvus collection not initialized"}
    
    try:
        # Test with a simple query
        test_query = "recent PRs"
        print(f"🧪 Testing search with query: '{test_query}'")
        
        # Generate embedding
        query_embedding = get_embedding(test_query)
        print(f"✅ Test embedding generated: {len(query_embedding)} dimensions")
        
        # Simple search without filters
        search_params = {
            "metric_type": "COSINE",
            "params": {"n_top": 5}
        }
        
        results = milvus_collection.search(
            data=[query_embedding],
            anns_field="vector",
            param=search_params,
            limit=5,
            output_fields=["pr_id", "pr_number", "title", "author_name"]
        )
        
        print(f"✅ Test search completed, found {len(results)} result sets")
        
        # Debug: Print hit object structure (only for first result)
        if results and len(results) > 0 and len(results[0]) > 0:
            first_hit = results[0][0]
            print(f"🔍 Debug: Found {len(results[0])} results in first set")
            print(f"🔍 Debug: Sample data - PR #{first_hit.fields.get('pr_number', 'N/A')}: {first_hit.fields.get('title', 'N/A')}")
        
        # Count total results
        total_results = sum(len(hits) for hits in results)
        
        return {
            "status": "success",
            "message": f"Search test successful",
            "query": test_query,
            "total_results": total_results,
            "sample_results": [
                {
                    "pr_id": hit.fields.get('pr_id', 0) if hasattr(hit, 'fields') else 0,
                    "pr_number": hit.fields.get('pr_number', 0) if hasattr(hit, 'fields') else 0,
                    "title": (hit.fields.get('title', '') or '')[:50] + "..." if hasattr(hit, 'fields') and len(hit.fields.get('title', '') or '') > 50 else (hit.fields.get('title', '') or '') if hasattr(hit, 'fields') else '',
                    "author": hit.fields.get('author_name', '') if hasattr(hit, 'fields') else '',
                    "score": round(hit.score, 3)
                }
                for hits in results
                for hit in hits[:2]  # Show first 2 results from each hit set
            ]
        }
        
    except Exception as e:
        print(f"❌ Test search failed: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            "status": "error",
            "message": f"Test search failed: {str(e)}",
            "traceback": traceback.format_exc()
        }

@app.get("/api/repositories")
async def get_repositories():
    """Get list of available repositories"""
    global milvus_collection
    
    if not milvus_collection:
        print("❌ Repositories endpoint: Milvus collection not initialized")
        raise HTTPException(
            status_code=500, 
            detail="Milvus collection not initialized. Please check your environment variables and Milvus connection."
        )
    
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
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch repositories: {str(e)}"
        )

@app.get("/what-shipped", response_class=HTMLResponse)
async def what_shipped_page(repo: str = Query(None, description="Selected repository")):
    """What Shipped page"""
    if not repo:
        raise HTTPException(status_code=400, detail="Repository parameter is required")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>What Shipped - What the repo</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                color: #ffffff;
                min-height: 100vh;
            }}
            
            .header {{
                background: rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(10px);
                padding: 1.5rem 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}
            
            .nav-container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 0 2rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .logo {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #00d4ff;
                text-decoration: none;
            }}
            
            .back-button {{
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 8px 16px;
                border-radius: 20px;
                text-decoration: none;
                transition: all 0.3s ease;
            }}
            
            .back-button:hover {{
                background: rgba(255, 255, 255, 0.2);
            }}
            
            .main-content {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 3rem 2rem;
            }}
            
            .page-title {{
                text-align: center;
                margin-bottom: 3rem;
            }}
            
            .page-title h1 {{
                font-size: 3rem;
                margin-bottom: 1rem;
                background: linear-gradient(45deg, #00d4ff, #ff6b6b);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            
            .page-title p {{
                font-size: 1.2rem;
                color: #b0b0b0;
                margin-bottom: 1rem;
            }}
            
            .repo-info {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 1.5rem;
                margin-bottom: 2rem;
                text-align: center;
                backdrop-filter: blur(10px);
            }}
            
            .repo-info h3 {{
                color: #00d4ff;
                font-size: 1.3rem;
                margin-bottom: 0.5rem;
            }}
            
            .repo-info p {{
                color: #b0b0b0;
                font-size: 1rem;
            }}
            
            .filters-section {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2rem;
                margin-bottom: 2rem;
                backdrop-filter: blur(10px);
            }}
            
            .filters-section h2 {{
                font-size: 1.8rem;
                margin-bottom: 1rem;
                color: #ffffff;
                text-align: center;
            }}
            
            .filters-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .filter-group {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }}
            
            .filter-group label {{
                font-size: 0.9rem;
                color: #b0b0b0;
                font-weight: 500;
            }}
            
            .filter-select {{
                padding: 10px 15px;
                background: rgba(255, 255, 255, 0.1);
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                color: #ffffff;
                font-size: 1rem;
                cursor: pointer;
                transition: all 0.3s ease;
                backdrop-filter: blur(10px);
            }}
            
            .filter-select:focus {{
                outline: none;
                border-color: #00d4ff;
                box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
            }}
            
            .filter-select option {{
                background: #1a1a2e;
                color: #ffffff;
                padding: 8px 12px;
            }}
            
            .filter-checkbox {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-top: 0.5rem;
            }}
            
            .filter-checkbox input[type="checkbox"] {{
                width: 18px;
                height: 18px;
                accent-color: #00d4ff;
            }}
            
            .apply-filters {{
                background: linear-gradient(45deg, #00d4ff, #ff6b6b);
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 10px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                display: block;
                margin: 0 auto;
            }}
            
            .apply-filters:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(0, 212, 255, 0.3);
            }}
            
            .summary-section {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2rem;
                margin-bottom: 2rem;
                backdrop-filter: blur(10px);
            }}
            
            .summary-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1.5rem;
            }}
            
            .summary-card {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 1.5rem;
                text-align: center;
                transition: all 0.3s ease;
            }}
            
            .summary-card:hover {{
                border-color: rgba(255, 255, 255, 0.2);
                transform: translateY(-5px);
            }}
            
            .summary-value {{
                font-size: 2.5rem;
                font-weight: bold;
                margin-bottom: 0.5rem;
            }}
            
            .summary-label {{
                font-size: 1rem;
                color: #b0b0b0;
            }}
            
            .total-prs .summary-value {{ color: #00d4ff; }}
            .features .summary-value {{ color: #4ecdc4; }}
            .high-risk .summary-value {{ color: #ff6b6b; }}
            .merged .summary-value {{ color: #ffd93d; }}
            
            .prs-section {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2rem;
                backdrop-filter: blur(10px);
            }}
            
            .prs-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2rem;
                flex-wrap: wrap;
                gap: 1rem;
            }}
            
            .prs-header h2 {{
                font-size: 1.8rem;
                color: #ffffff;
            }}
            
            .prs-count {{
                color: #b0b0b0;
                font-size: 1rem;
            }}
            
            .prs-grid {{
                display: grid;
                gap: 1.5rem;
            }}
            
            .pr-card {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 1.5rem;
                transition: all 0.3s ease;
                cursor: pointer;
            }}
            
            .pr-card:hover {{
                border-color: rgba(255, 255, 255, 0.2);
                transform: translateY(-3px);
            }}
            
            .pr-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 1rem;
                gap: 1rem;
            }}
            
            .pr-title {{
                font-size: 1.2rem;
                font-weight: 600;
                color: #ffffff;
                flex: 1;
            }}
            
            .pr-number {{
                background: rgba(0, 212, 255, 0.2);
                color: #00d4ff;
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 0.9rem;
                font-weight: 600;
            }}
            
            .pr-meta {{
                display: flex;
                gap: 1rem;
                margin-bottom: 1rem;
                flex-wrap: wrap;
            }}
            
            .pr-author {{
                color: #4ecdc4;
                font-weight: 500;
            }}
            
            .pr-date {{
                color: #b0b0b0;
                font-size: 0.9rem;
            }}
            
            .pr-summary {{
                color: #b0b0b0;
                line-height: 1.6;
                margin-bottom: 1rem;
            }}
            
            .pr-stats {{
                display: flex;
                gap: 1rem;
                margin-bottom: 1rem;
                flex-wrap: wrap;
            }}
            
            .pr-stat {{
                background: rgba(255, 255, 255, 0.1);
                padding: 6px 12px;
                border-radius: 8px;
                font-size: 0.9rem;
                color: #ffffff;
            }}
            
            .pr-labels {{
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
            }}
            
            .pr-label {{
                padding: 4px 8px;
                border-radius: 6px;
                font-size: 0.8rem;
                font-weight: 500;
            }}
            
            .label-feature {{ background: rgba(78, 205, 196, 0.2); color: #4ecdc4; }}
            .label-high-risk {{ background: rgba(255, 107, 107, 0.2); color: #ff6b6b; }}
            .label-medium-risk {{ background: rgba(255, 217, 61, 0.2); color: #ffd93d; }}
            .label-low-risk {{ background: rgba(0, 212, 255, 0.2); color: #00d4ff; }}
            .label-merged {{ background: rgba(78, 205, 196, 0.2); color: #4ecdc4; }}
            .label-closed {{ background: rgba(255, 107, 107, 0.2); color: #ff6b6b; }}
            .label-open {{ background: rgba(255, 217, 61, 0.2); color: #ffd93d; }}
            
            .loading {{
                text-align: center;
                padding: 3rem;
                color: #b0b0b0;
            }}
            
            .error {{
                background: rgba(255, 107, 107, 0.1);
                border: 1px solid rgba(255, 107, 107, 0.3);
                border-radius: 10px;
                padding: 1rem;
                color: #ff6b6b;
                text-align: center;
            }}
            
            @media (max-width: 768px) {{
                .filters-grid {{
                    grid-template-columns: 1fr;
                }}
                
                .summary-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
                
                .pr-header {{
                    flex-direction: column;
                    align-items: flex-start;
                }}
                
                .pr-meta {{
                    flex-direction: column;
                    gap: 0.5rem;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="nav-container">
                <a href="/" class="logo">What the repo-gpt</a>
                <a href="/" class="back-button">← Back to Home</a>
            </div>
        </div>
        
        <div class="main-content">
            <div class="page-title">
                <h1>What Shipped</h1>
                <p>Discover recent features and improvements across your repositories</p>
                <div class="repo-info">
                    <h3>Repository</h3>
                    <p>{repo}</p>
                </div>
            </div>
            
            <div class="filters-section">
                <h2>Filters & Time Range</h2>
                <div class="filters-grid">
                    <div class="filter-group">
                        <label for="timeWindow">Time Window</label>
                        <select id="timeWindow" class="filter-select">
                            <option value="7d">Last 7 days</option>
                            <option value="30d" selected>Last 30 days</option>
                            <option value="90d">Last 90 days</option>
                            <option value="all">All time</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="authorFilter">Author</label>
                        <select id="authorFilter" class="filter-select">
                            <option value="">All authors</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label for="riskFilter">Risk Level</label>
                        <select id="riskFilter" class="filter-select">
                            <option value="">All risk levels</option>
                            <option value="low">Low risk</option>
                            <option value="medium">Medium risk</option>
                            <option value="high">High risk</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <div class="filter-checkbox">
                            <input type="checkbox" id="featureOnly">
                            <label for="featureOnly">Features only</label>
                        </div>
                    </div>
                </div>
                <button class="apply-filters" onclick="loadData()">Apply Filters</button>
            </div>
            
            <div class="summary-section">
                <div class="summary-grid">
                    <div class="summary-card total-prs">
                        <div class="summary-value" id="totalPrs">-</div>
                        <div class="summary-label">Total PRs</div>
                    </div>
                    <div class="summary-card features">
                        <div class="summary-value" id="totalFeatures">-</div>
                        <div class="summary-label">Features</div>
                    </div>
                    <div class="summary-card high-risk">
                        <div class="summary-value" id="totalHighRisk">-</div>
                        <div class="summary-label">High Risk</div>
                    </div>
                    <div class="summary-card merged">
                        <div class="summary-value" id="totalMerged">-</div>
                        <div class="summary-label">Merged</div>
                    </div>
                </div>
            </div>
            
            <div class="prs-section">
                <div class="prs-header">
                    <h2>Pull Requests</h2>
                    <div class="prs-count" id="prsCount">Loading...</div>
                </div>
                <div id="prsContainer" class="prs-grid">
                    <div class="loading">Loading pull requests...</div>
                </div>
            </div>
        </div>
        
        <script>
            let currentRepo = '{repo}';
            
            async function loadAuthors() {{
                try {{
                    const response = await fetch(`/api/what-shipped-authors?repo=${{currentRepo}}`);
                    const data = await response.json();
                    
                    const authorSelect = document.getElementById('authorFilter');
                    authorSelect.innerHTML = '<option value="">All authors</option>';
                    
                    data.authors.forEach(author => {{
                        const option = document.createElement('option');
                        option.value = author.username;
                        option.textContent = author.username;
                        authorSelect.appendChild(option);
                    }});
                    
                    console.log(`Loaded ${{data.total}} authors for ${{currentRepo}}`);
                }} catch (error) {{
                    console.error('Error loading authors:', error);
                }}
            }}
            
            async function loadData() {{
                const timeWindow = document.getElementById('timeWindow').value;
                const author = document.getElementById('authorFilter').value;
                const riskLevel = document.getElementById('riskFilter').value;
                const featureOnly = document.getElementById('featureOnly').checked;
                
                // Show loading state
                document.getElementById('prsContainer').innerHTML = '<div class="loading">Loading pull requests...</div>';
                
                try {{
                    // Load summary data
                    const summaryResponse = await fetch(`/api/what-shipped-summary?repo=${{currentRepo}}&time_window=${{timeWindow}}`);
                    const summaryData = await summaryResponse.json();
                    
                    // Update summary cards
                    document.getElementById('totalPrs').textContent = summaryData.total_prs;
                    document.getElementById('totalFeatures').textContent = summaryData.features;
                    document.getElementById('totalHighRisk').textContent = summaryData.high_risk;
                    document.getElementById('totalMerged').textContent = summaryData.merged;
                    
                    // Load PR data
                    const params = new URLSearchParams({{
                        repo: currentRepo,
                        time_window: timeWindow,
                        limit: 50
                    }});
                    
                    if (author) params.append('author', author);
                    if (riskLevel) params.append('risk_level', riskLevel);
                    if (featureOnly) params.append('feature_only', 'true');
                    
                    const prsResponse = await fetch(`/api/what-shipped-data?${{params}}`);
                    const prsData = await prsResponse.json();
                    
                    // Update PR count
                    document.getElementById('prsCount').textContent = `${{prsData.total}} PRs`;
                    
                    // Render PRs
                    renderPRs(prsData.data);
                    
                }} catch (error) {{
                    console.error('Error loading data:', error);
                    document.getElementById('prsContainer').innerHTML = '<div class="error">Error loading data. Please try again.</div>';
                }}
            }}
            
            function renderPRs(prs) {{
                const container = document.getElementById('prsContainer');
                
                if (!prs || prs.length === 0) {{
                    container.innerHTML = '<div class="loading">No pull requests found for the selected filters.</div>';
                    return;
                }}
                
                container.innerHTML = prs.map(pr => `
                    <div class="pr-card" onclick="showPRDetails(${{pr.pr_number}})">
                        <div class="pr-header">
                            <div class="pr-title">${{pr.title}}</div>
                            <div class="pr-number">#${{pr.pr_number}}</div>
                        </div>
                        <div class="pr-meta">
                            <span class="pr-author">by ${{pr.author}}</span>
                            <span class="pr-date">${{formatDate(pr.merged_at || pr.created_at)}}</span>
                        </div>
                        ${{pr.pr_summary ? `<div class="pr-summary">${{pr.pr_summary.substring(0, 200)}}${{pr.pr_summary.length > 200 ? '...' : ''}}</div>` : ''}}
                        <div class="pr-stats">
                            <div class="pr-stat">+${{pr.additions}} -${{pr.deletions}}</div>
                            <div class="pr-stat">${{pr.changed_files}} files</div>
                            <div class="pr-stat">Risk: ${{pr.risk_score.toFixed(1)}}</div>
                        </div>
                        <div class="pr-labels">
                            ${{getLabelsHTML(pr)}}
                        </div>
                    </div>
                `).join('');
            }}
            
            function getLabelsHTML(pr) {{
                const labels = [];
                
                // Risk labels
                if (pr.high_risk) {{
                    labels.push('<span class="pr-label label-high-risk">High Risk</span>');
                }} else if (pr.risk_score >= 4.0) {{
                    labels.push('<span class="pr-label label-medium-risk">Medium Risk</span>');
                }} else {{
                    labels.push('<span class="pr-label label-low-risk">Low Risk</span>');
                }}
                
                // Feature labels
                if (pr.feature_rule !== 'excluded') {{
                    labels.push('<span class="pr-label label-feature">Feature</span>');
                }}
                
                // Status labels
                if (pr.is_merged) {{
                    labels.push('<span class="pr-label label-merged">Merged</span>');
                }} else {{
                    labels.push('<span class="pr-label label-closed">Closed</span>');
                }}
                
                return labels.join('');
            }}
            
            function formatDate(dateString) {{
                if (!dateString) return 'Unknown';
                const date = new Date(dateString);
                return date.toLocaleDateString('en-US', {{ 
                    year: 'numeric', 
                    month: 'short', 
                    day: 'numeric' 
                }});
            }}
            
            function showPRDetails(prNumber) {{
                // You can implement PR details modal or navigation here
                console.log('Show PR details for:', prNumber);
            }}
            
            // Load data on page load
            document.addEventListener('DOMContentLoaded', function() {{
                loadAuthors();
                loadData();
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/engineering-lens", response_class=HTMLResponse)
async def engineering_lens_page(repo: str = Query(None, description="Selected repository")):
    """Engineer Lens page"""
    if not repo:
        raise HTTPException(status_code=400, detail="Repository parameter is required")
    
    if not engineer_lens_ui:
        raise HTTPException(status_code=500, detail="Engineer Lens UI not initialized")
    
    html_content = engineer_lens_ui.get_engineer_lens_html(repo)
    return HTMLResponse(content=html_content)

@app.get("/api/example-queries")
async def get_example_queries(repo: str = Query(None, description="Selected repository")):
    """Get example queries for a specific repository"""
    if not repo:
        raise HTTPException(status_code=400, detail="Repository name is required for example queries")

    try:
        # In a real application, you might fetch these from a database or a config file
        # For now, we'll return a few generic ones or ones specific to the repo if available
        example_queries = [
            {"query": "What was shipped in the last two weeks?", "type": "Time-based", "description": "Find PRs merged in the last 14 days with features and improvements.", "tags": ["time", "last_two_weeks", "shipped"]},
            {"query": "Show me high risk code changes", "type": "Risk-based", "description": "Find code changes with high risk scores and potential issues.", "tags": ["risk", "high_risk", "code"]},
            {"query": "What are the most recent features?", "type": "Feature-based", "description": "Find recent PRs that represent new features or enhancements.", "tags": ["feature", "recent", "enhancement"]},
            {"query": "Find changes by author john_doe", "type": "Author-based", "description": "Search for code changes authored by a specific user.", "tags": ["author", "john_doe"]},
            {"query": "Show me all merged changes from this year", "type": "Status-based", "description": "List all merged PRs from the current year.", "tags": ["status", "merged", "this_year"]},
            {"query": "What files were changed recently?", "type": "File-based", "description": "Get detailed file information for recent changes.", "tags": ["files", "recent", "details"]},
            {"query": "Find database schema changes", "type": "Code-based", "description": "Search for changes related to database schemas and migrations.", "tags": ["database", "schema", "migration"]},
            {"query": "Show me API changes", "type": "Code-based", "description": "Find changes related to API endpoints and interfaces.", "tags": ["api", "endpoints", "interface"]}
        ]

        # If a specific repo is requested, we can filter or return more repo-specific examples
        if repo:
            # For demonstration, we'll return a subset of the generic ones
            repo_specific_examples = [
                {"query": f"What was shipped in {repo} last week?", "type": "Time-based", "description": f"Find PRs shipped in {repo} last 7 days.", "tags": ["time", "last_week", repo]},
                {"query": f"Find PRs by author John Doe in {repo}", "type": "Author-based", "description": f"Search for PRs authored by a specific user in {repo}.", "tags": ["author", "john_doe", repo]},
                {"query": f"What are the top 5 riskiest PRs in {repo}?", "type": "Risk-based", "description": f"Identify PRs with the highest risk scores in {repo}.", "tags": ["risk", "top_risk", repo]},
                {"query": f"Show me all merged PRs from last month in {repo}", "type": "Status-based", "description": f"List all merged PRs from the last 30 days in {repo}.", "tags": ["status", "merged", "last_month", repo]},
                {"query": f"What are the most recent PRs in {repo}?", "type": "Recent-based", "description": f"Find the latest PRs in {repo}.", "tags": ["recent", "latest", repo]}
            ]
            example_queries = repo_specific_examples

        return {"queries": example_queries}
    except Exception as e:
        print(f"Error fetching example queries: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch example queries: {e}")

@app.get("/api/search")
async def search_prs_get(
    query: str = Query(..., description="Search query"),
    repo_name: str = Query(None, description="Repository name"),
    limit: int = Query(10, description="Number of results to return")
):
    """Search PRs using GET request (for frontend compatibility)"""
    search_request = SearchRequest(query=query, repo_name=repo_name, limit=limit)
    return await search_prs(search_request)

@app.post("/search")
async def search_prs(request: SearchRequest):
    """Search PRs using vector similarity with natural language processing"""
    if not milvus_collection:
        raise HTTPException(status_code=500, detail="Milvus collection not initialized")
    
    try:
        print(f"🔍 Search request: query='{request.query}', repo='{request.repo_name}', limit={request.limit}")
        
        # Parse the natural language query to extract filters
        query_filters = parse_natural_language_query(request.query)
        print(f"📋 Parsed filters: {query_filters}")
        
        # Debug: Show what each filter does
        if query_filters.get('feature_filter'):
            print(f"🔍 Feature filter: {query_filters['feature_filter']}")
        if query_filters.get('time_filter'):
            print(f"🔍 Time filter: {query_filters['time_filter']}")
        if query_filters.get('status_filter'):
            print(f"🔍 Status filter: {query_filters['status_filter']}")
        
        # Build search expression with filters
        expr_parts = []
        
        # Repository filter
        if request.repo_name:
            expr_parts.append(f'repo_name == "{request.repo_name}"')
        
        # Time-based filters
        if query_filters.get('time_filter'):
            time_expr = query_filters['time_filter']
            expr_parts.append(time_expr)
        
        # Status filters
        if query_filters.get('status_filter'):
            status_expr = query_filters['status_filter']
            expr_parts.append(status_expr)
        
        # Author filters
        if query_filters.get('author_filter'):
            author_expr = query_filters['author_filter']
            expr_parts.append(author_expr)
        
        # Risk-based filters
        if query_filters.get('risk_filter'):
            risk_expr = query_filters['risk_filter']
            expr_parts.append(risk_expr)
        
        # Feature filters
        if query_filters.get('feature_filter'):
            feature_expr = query_filters['feature_filter']
            expr_parts.append(feature_expr)
        
        # Combine all expressions
        expr = " and ".join(expr_parts) if expr_parts else None
        print(f"🔍 Search expression: {expr}")
        
        # Determine search method
        use_direct_query = query_filters.get('use_direct_query', False)
        
        if use_direct_query:
            print(f"🔍 Using DIRECT QUERY method for filtered search")
            # Use direct query for specific filtered requests
            try:
                results = milvus_collection.query(
                    expr=expr,
                    output_fields=["pr_id", "pr_number", "title", "body", "author_name", "created_at", "merged_at", "status", "repo_name", "is_merged", "is_closed", "feature", "pr_summary", "risk_score", "risk_band", "risk_reasons", "additions", "deletions", "changed_files"],
                    limit=request.limit
                )
                print(f"✅ Direct query completed, found {len(results)} results")
                
                # Convert to search result format with deduplication
                search_results = []
                seen_pr_ids = set()
                seen_pr_numbers = set()
                duplicates_skipped = 0
                
                for result in results:
                    pr_id = result.get('pr_id', 0)
                    pr_number = result.get('pr_number', 0)
                    
                    # Deduplication check
                    is_duplicate = False
                    if pr_id in seen_pr_ids:
                        print(f"🔍 Direct query: Skipping duplicate PR #{pr_number} (ID: {pr_id}) - already seen")
                        is_duplicate = True
                        duplicates_skipped += 1
                    elif pr_number in seen_pr_numbers:
                        print(f"🔍 Direct query: Skipping duplicate PR #{pr_number} (ID: {pr_id}) - PR number already seen")
                        is_duplicate = True
                        duplicates_skipped += 1
                    
                    if is_duplicate:
                        continue
                    
                    seen_pr_ids.add(pr_id)
                    seen_pr_numbers.add(pr_number)
                    
                    search_results.append(SearchResult(
                        pr_id=pr_id,
                        pr_number=pr_number,
                        title=result.get('title', '') or '',
                        content=result.get('body', '') or '',
                        text_type="pr_data",
                        file_path="",
                        function_name="",
                        similarity_score=1.0,  # Direct query results have max similarity
                        author=result.get('author_name', '') or '',
                        created_at=result.get('created_at', 0) or 0,
                        merged_at=result.get('merged_at', 0) or 0,
                        status=result.get('status', '') or '',
                        is_merged=result.get('is_merged', False) or False,
                        is_closed=result.get('is_closed', False) or False,
                        feature=result.get('feature', '') or '',
                        pr_summary=result.get('pr_summary', '') or '',
                        risk_score=float(result.get('risk_score', 0.0) or 0.0),
                        risk_band=result.get('risk_band', 'low') or 'low',
                        risk_reasons=result.get('risk_reasons', []) or [],
                        additions=result.get('additions', 0) or 0,
                        deletions=result.get('deletions', 0) or 0,
                        changed_files=result.get('changed_files', 0) or 0,
                        file_details=[]
                    ))
                
                print(f"✅ Direct query processed {len(search_results)} results (skipped {duplicates_skipped} duplicates)")
                return search_results
                
            except Exception as direct_query_error:
                print(f"❌ Direct query failed: {direct_query_error}")
                # Fall back to vector search
                print(f"🔄 Falling back to vector search")
        
        # Use vector similarity search for semantic queries
        print(f"🔍 Using VECTOR SEARCH method for semantic query")
        
        # Generate embedding for the query
        try:
            query_embedding = get_embedding(request.query)
            print(f"✅ Generated embedding with {len(query_embedding)} dimensions")
        except Exception as embed_error:
            print(f"❌ Embedding generation failed: {embed_error}")
            raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {embed_error}")
        
        # Search parameters
        search_params = {
            "metric_type": "COSINE",
            "params": {"n_top": request.limit}
        }
        
        print(f"🔍 Performing Milvus vector search with params: {search_params}")
        
        # Perform vector search
        try:
            results = milvus_collection.search(
            data=[query_embedding],
            anns_field="vector",
            param=search_params,
            limit=request.limit,
            expr=expr,
                output_fields=["pr_id", "pr_number", "title", "body", "author_name", "created_at", "merged_at", "status", "repo_name", "is_merged", "is_closed", "feature", "pr_summary", "risk_score", "risk_band", "risk_reasons", "additions", "deletions", "changed_files"]
            )
            print(f"✅ Milvus search completed, found {len(results)} result sets")
            
            # Convert results to list to avoid iteration issues
            results_list = list(results)
            
            # Debug: Print detailed result information
            total_hits = sum(len(list(hits)) for hits in results_list)
            print(f"🔍 Total hits across all result sets: {total_hits}")
            
            # Debug: Print hit object structure (only for first result)
            if results_list and len(results_list) > 0:
                # Convert the first result set to list as well
                first_result_set = list(results_list[0])
                if len(first_result_set) > 0:
                    first_hit = first_result_set[0]
                    print(f"🔍 Debug: Found {len(first_result_set)} results in first set")
                    print(f"🔍 Debug: Sample data - PR #{first_hit.fields.get('pr_number', 'N/A')}: {first_hit.fields.get('title', 'N/A')}")
                    
                    # Show all PR numbers in first result set
                    pr_numbers = [hit.fields.get('pr_number', 'N/A') for hit in first_result_set]
                    print(f"🔍 PR numbers in first result set: {pr_numbers}")
                    
                    # Show unique PR numbers and their counts
                    from collections import Counter
                    pr_counter = Counter(pr_numbers)
                    print(f"🔍 PR number frequency: {dict(pr_counter)}")
        except Exception as search_error:
            print(f"❌ Milvus search failed: {search_error}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Milvus search failed: {search_error}")
        
        search_results = []
        seen_pr_ids = set()  # Track seen PR IDs to avoid duplicates
        seen_pr_numbers = set()  # Track seen PR numbers as backup
        total_hits_processed = 0
        duplicates_skipped = 0
        
        try:
            for hits in results_list:
                # Convert each result set to list to avoid iteration issues
                hits_list = list(hits)
                for hit in hits_list:
                    total_hits_processed += 1
                    # Extract fields with safe defaults - Use hit.fields for Milvus Hit objects
                    hit_data = hit.fields if hasattr(hit, 'fields') else {}
                    pr_id = hit_data.get('pr_id', 0)
                    pr_number = hit_data.get('pr_number', 0)
                    title = hit_data.get('title', '') or ''
                    body = hit_data.get('body', '') or ''
                    author_name = hit_data.get('author_name', '') or ''
                    created_at = hit_data.get('created_at', 0) or 0
                    merged_at = hit_data.get('merged_at', 0) or 0
                    status = hit_data.get('status', '') or ''
                    repo_name = hit_data.get('repo_name', '') or ''
                    is_merged = hit_data.get('is_merged', False) or False
                    is_closed = hit_data.get('is_closed', False) or False
                    feature = hit_data.get('feature', '') or ''
                    pr_summary = hit_data.get('pr_summary', '') or ''
                    risk_score = float(hit_data.get('risk_score', 0.0) or 0.0)
                    risk_band = hit_data.get('risk_band', 'low') or 'low'
                    risk_reasons = hit_data.get('risk_reasons', []) or []
                    additions = hit_data.get('additions', 0) or 0
                    deletions = hit_data.get('deletions', 0) or 0
                    changed_files = hit_data.get('changed_files', 0) or 0
                    
                    # Get detailed file information if requested
                    file_details = []
                    if query_filters.get('include_file_details'):
                        try:
                            file_details = await get_file_details_for_pr(pr_id, repo_name)
                        except Exception as file_error:
                            print(f"⚠️ Warning: Failed to get file details for PR {pr_id}: {file_error}")
                            file_details = []
                    
                    # Additional safety check: for "shipped" queries, only include merged PRs with features
                    should_include = True
                    if 'shipped' in request.query.lower():
                        if not is_merged or not feature:
                            should_include = False
                            print(f"🔍 Filtering out PR #{pr_number}: not merged ({is_merged}) or no feature ({bool(feature)})")
                    
                    # Enhanced deduplication check
                    is_duplicate = False
                    if pr_id in seen_pr_ids:
                        print(f"🔍 Skipping duplicate PR #{pr_number} (ID: {pr_id}) - already seen")
                        is_duplicate = True
                        duplicates_skipped += 1
                    elif pr_number in seen_pr_numbers:
                        print(f"🔍 Skipping duplicate PR #{pr_number} (ID: {pr_id}) - PR number already seen")
                        is_duplicate = True
                        duplicates_skipped += 1
                    
                    if is_duplicate:
                        continue
                    
                    if should_include:
                        seen_pr_ids.add(pr_id)  # Mark this PR as seen
                        seen_pr_numbers.add(pr_number)  # Mark PR number as seen
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
                            file_details=file_details
                        ))
            
            print(f"✅ Processed {len(search_results)} search results (after deduplication)")
            print(f"🔍 Deduplication stats: {total_hits_processed} total hits processed, {duplicates_skipped} duplicates skipped")
            
            # Print summary of results
            if search_results:
                print(f"📊 Search Summary:")
                print(f"   - Total results: {len(search_results)}")
                print(f"   - Unique PRs: {len(seen_pr_ids)}")
                print(f"   - Date range: {min(r.created_at for r in search_results)} to {max(r.created_at for r in search_results)}")
                print(f"   - Risk distribution: {sum(1 for r in search_results if r.risk_band == 'high')} high, {sum(1 for r in search_results if r.risk_band == 'medium')} medium, {sum(1 for r in search_results if r.risk_band == 'low')} low")
                print(f"   - Features found: {sum(1 for r in search_results if r.feature)}")
            
            return search_results
            
        except Exception as process_error:
            print(f"❌ Error processing search results: {process_error}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error processing search results: {process_error}")
    except Exception as e:
        print(f"Error performing search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

def parse_natural_language_query(query: str) -> dict:
    """Parse natural language query to extract filters"""
    query_lower = query.lower()
    filters = {}
    
    # Time-based filters
    if any(phrase in query_lower for phrase in ['last week', 'past week', '7 days']):
        import time
        week_ago = int(time.time()) - (7 * 24 * 60 * 60)
        filters['time_filter'] = f'created_at >= {week_ago}'
    elif any(phrase in query_lower for phrase in ['last month', 'past month', '30 days']):
        import time
        month_ago = int(time.time()) - (30 * 24 * 60 * 60)
        filters['time_filter'] = f'created_at >= {month_ago}'
    elif any(phrase in query_lower for phrase in ['last two weeks', 'past two weeks', '14 days']):
        import time
        two_weeks_ago = int(time.time()) - (14 * 24 * 60 * 60)
        filters['time_filter'] = f'created_at >= {two_weeks_ago}'
    elif any(phrase in query_lower for phrase in ['this year', '2024', '2025']):
        import time
        year_start = int(time.time()) - (365 * 24 * 60 * 60)  # Approximate
        filters['time_filter'] = f'created_at >= {year_start}'
    
    # Status filters
    if 'merged' in query_lower:
        filters['status_filter'] = 'is_merged == true'
    elif 'closed' in query_lower and 'merged' not in query_lower:
        filters['status_filter'] = 'is_closed == true and is_merged == false'
    elif 'open' in query_lower:
        filters['status_filter'] = 'is_closed == false'
    
    # Author filters
    if 'by author' in query_lower or 'author:' in query_lower:
        # Extract author name (simplified)
        import re
        author_match = re.search(r'by author\s+([a-zA-Z0-9_-]+)', query_lower)
        if author_match:
            author_name = author_match.group(1)
            filters['author_filter'] = f'author_name == "{author_name}"'
    
    # Risk-based filters
    if 'riskiest' in query_lower or 'high risk' in query_lower:
        filters['risk_filter'] = 'risk_score >= 7.0'
    elif 'low risk' in query_lower:
        filters['risk_filter'] = 'risk_score <= 3.0'
    elif 'medium risk' in query_lower:
        filters['risk_filter'] = 'risk_score > 3.0 and risk_score < 7.0'
    
    # Feature filters
    if 'feature' in query_lower or 'shipped' in query_lower:
        # For "shipped" queries, we want merged features
        if 'shipped' in query_lower:
            filters['feature_filter'] = 'feature != "" and is_merged == true'
        else:
            filters['feature_filter'] = 'feature != ""'
    
    # File details flag
    if any(phrase in query_lower for phrase in ['file details', 'files changed', 'what files']):
        filters['include_file_details'] = True
    
    # Determine if this should use direct query instead of vector search
    # Use direct query for specific filtered requests
    if any(phrase in query_lower for phrase in ['all', 'every', 'list', 'show me', 'find all', 'get all']):
        filters['use_direct_query'] = True
    
    return filters

async def get_file_details_for_pr(pr_id: int, repo_name: str) -> list:
    """Get detailed file information for a PR from the file collection"""
    global milvus_collection
    
    try:
        # Query the file collection for this PR
        file_collection_name = 'file_changes_what_the_repo'
        
        if not utility.has_collection(file_collection_name):
            return []
        
        file_collection = Collection(file_collection_name)
        file_collection.load()
        
        # Query for files in this PR
        file_results = file_collection.query(
            expr=f'pr_id == {pr_id} and repo_name == "{repo_name}"',
            output_fields=["file_id", "file_status", "language", "additions", "deletions", "lines_changed", "ai_summary", "risk_score_file", "high_risk_flag"],
            limit=100
        )
        
        return file_results
    except Exception as e:
        print(f"Error getting file details for PR {pr_id}: {e}")
        return []

@app.get("/pr-details", response_class=HTMLResponse)
async def pr_details_page(
    pr_id: int = Query(..., description="PR ID"),
    repo: str = Query(..., description="Repository name")
):
    """PR Details page showing comprehensive PR information"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PR Details - What the repo-gpt</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                color: #ffffff;
                min-height: 100vh;
            }}
            
            .header {{
                background: rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(10px);
                padding: 1rem 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}
            
            .nav-container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 0 2rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .logo {{
                font-size: 1.5rem;
                font-weight: 700;
                color: #00d4ff;
                text-decoration: none;
            }}
            
            .back-button {{
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 8px 16px;
                border-radius: 20px;
                text-decoration: none;
                transition: all 0.3s ease;
            }}
            
            .back-button:hover {{
                background: rgba(255, 255, 255, 0.2);
            }}
            
            .main-content {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 2rem;
            }}
            
            .pr-header {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 2rem;
                margin-bottom: 2rem;
                backdrop-filter: blur(10px);
            }}
            
            .pr-title {{
                font-size: 2rem;
                margin-bottom: 1rem;
                color: #00d4ff;
            }}
            
            .pr-meta {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .meta-item {{
                background: rgba(255, 255, 255, 0.05);
                padding: 1rem;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}
            
            .meta-label {{
                font-size: 0.8rem;
                color: #b0b0b0;
                text-transform: uppercase;
                margin-bottom: 0.5rem;
            }}
            
            .meta-value {{
                font-size: 1rem;
                font-weight: 600;
            }}
            
            .pr-summary {{
                background: rgba(0, 212, 255, 0.1);
                border: 1px solid rgba(0, 212, 255, 0.3);
                border-radius: 8px;
                padding: 1.5rem;
                margin: 1.5rem 0;
                color: #00d4ff;
                font-size: 1rem;
                line-height: 1.6;
            }}
            
            .pr-content {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 2rem;
                margin-bottom: 2rem;
                backdrop-filter: blur(10px);
            }}
            
            .content-title {{
                font-size: 1.5rem;
                margin-bottom: 1rem;
                color: #ffffff;
            }}
            
            .pr-body {{
                background: rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                padding: 1.5rem;
                margin: 1rem 0;
                line-height: 1.6;
                white-space: pre-wrap;
                max-height: 400px;
                overflow-y: auto;
            }}
            
            .risk-section {{
                background: rgba(255, 193, 7, 0.1);
                border-left: 4px solid #ffc107;
                border-radius: 8px;
                padding: 1.5rem;
                margin: 1.5rem 0;
                color: #ffd54f;
            }}
            
            .risk-factors ul {{
                margin: 0.5rem 0 0 0;
                padding-left: 1.5rem;
            }}
            
            .risk-factors li {{
                margin: 0.25rem 0;
                color: #ffd54f;
            }}
            
            .files-section {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                padding: 2rem;
                margin-bottom: 2rem;
                backdrop-filter: blur(10px);
            }}
            
            .file-item {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 1.5rem;
                margin-bottom: 1rem;
                transition: all 0.3s ease;
            }}
            
            .file-item:hover {{
                border-color: rgba(255, 255, 255, 0.2);
                transform: translateY(-2px);
            }}
            
            .file-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }}
            
            .file-name {{
                font-size: 1.1rem;
                font-weight: 600;
                color: #00d4ff;
            }}
            
            .file-status {{
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.8rem;
                font-weight: 600;
            }}
            
            .status-added {{
                background: rgba(76, 175, 80, 0.2);
                color: #4caf50;
            }}
            
            .status-modified {{
                background: rgba(255, 193, 7, 0.2);
                color: #ffc107;
            }}
            
            .status-removed {{
                background: rgba(244, 67, 54, 0.2);
                color: #f44336;
            }}
            
            .file-meta {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 1rem;
                margin-bottom: 1rem;
            }}
            
            .file-ai-summary {{
                background: rgba(76, 175, 80, 0.1);
                border: 1px solid rgba(76, 175, 80, 0.3);
                border-radius: 8px;
                padding: 1rem;
                margin: 1rem 0;
                color: #4caf50;
                font-style: italic;
            }}
            
            .file-risk {{
                background: rgba(255, 193, 7, 0.1);
                border-left: 4px solid #ffc107;
                border-radius: 8px;
                padding: 1rem;
                margin: 1rem 0;
                color: #ffd54f;
            }}
            
            .loading {{
                text-align: center;
                color: #00d4ff;
                font-style: italic;
                padding: 2rem;
            }}
            
            .error {{
                text-align: center;
                color: #ff6b6b;
                font-style: italic;
                padding: 2rem;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="nav-container">
                <a href="/" class="logo">🔍 What the repo</a>
                <a href="/" class="back-button">← Back to Home</a>
            </div>
        </div>
        
        <div class="main-content">
            <div id="pr-details">
                <div class="loading">Loading PR details...</div>
            </div>
        </div>

        <script>
            const prId = {pr_id};
            const repoName = '{repo}';
            
            async function loadPRDetails() {{
                try {{
                    const response = await fetch(`/api/pr-details?pr_id=${{prId}}&repo=${{encodeURIComponent(repoName)}}`);
                    if (!response.ok) {{
                        throw new Error('Failed to fetch PR details');
                    }}
                    
                    const data = await response.json();
                    displayPRDetails(data);
                }} catch (error) {{
                    console.error('Error loading PR details:', error);
                    document.getElementById('pr-details').innerHTML = '<div class="error">Failed to load PR details: ' + error.message + '</div>';
                }}
            }}
            
            function displayPRDetails(data) {{
                const container = document.getElementById('pr-details');
                
                // Format dates
                const createdDate = new Date(data.created_at * 1000).toLocaleDateString();
                const mergedDate = data.merged_at ? new Date(data.merged_at * 1000).toLocaleDateString() : 'Not merged';
                
                // Format risk factors
                const riskFactorsHtml = data.risk_reasons && data.risk_reasons.length > 0 
                    ? `<div class="risk-section"><strong>Risk Factors:</strong><ul>${{data.risk_reasons.map(reason => `<li>${{reason}}</li>`).join('')}}</ul></div>` 
                    : '';
                
                // Format files
                const filesHtml = data.file_details && data.file_details.length > 0 
                    ? data.file_details.map(file => {{
                        const statusClass = file.file_status === 'added' ? 'status-added' : 
                                          file.file_status === 'modified' ? 'status-modified' : 'status-removed';
                        
                        const aiSummaryHtml = file.ai_summary 
                            ? `<div class="file-ai-summary"><strong>AI Summary:</strong> ${{file.ai_summary}}</div>` 
                            : '';
                        
                        const fileRiskHtml = file.risk_score_file > 0 
                            ? `<div class="file-risk"><strong>Risk Score:</strong> ${{file.risk_score_file.toFixed(1)}}/10 ${{file.high_risk_flag ? '(High Risk)' : ''}}</div>` 
                            : '';
                        
                        return `
                            <div class="file-item">
                                <div class="file-header">
                                    <div class="file-name">${{file.file_id}}</div>
                                    <span class="file-status ${{statusClass}}">${{file.file_status.toUpperCase()}}</span>
                                </div>
                                <div class="file-meta">
                                    <div><strong>Language:</strong> ${{file.language || 'Unknown'}}</div>
                                    <div><strong>Additions:</strong> +${{file.additions}}</div>
                                    <div><strong>Deletions:</strong> -${{file.deletions}}</div>
                                    <div><strong>Lines Changed:</strong> ${{file.lines_changed}}</div>
                                </div>
                                ${{aiSummaryHtml}}
                                ${{fileRiskHtml}}
                            </div>
                        `;
                    }}).join('') 
                    : '<p>No file details available</p>';
                
                container.innerHTML = `
                    <div class="pr-header">
                        <h1 class="pr-title">${{data.title}}</h1>
                        <div class="pr-meta">
                            <div class="meta-item">
                                <div class="meta-label">PR Number</div>
                                <div class="meta-value">#${{data.pr_number}}</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Author</div>
                                <div class="meta-value">${{data.author}}</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Status</div>
                                <div class="meta-value">${{data.status}}</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Created</div>
                                <div class="meta-value">${{createdDate}}</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Merged</div>
                                <div class="meta-value">${{mergedDate}}</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Risk Level</div>
                                <div class="meta-value">${{data.risk_band.toUpperCase()}} (${{data.risk_score.toFixed(1)}}/10)</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Changes</div>
                                <div class="meta-value">+${{data.additions}} -${{data.deletions}}</div>
                            </div>
                            <div class="meta-item">
                                <div class="meta-label">Files Changed</div>
                                <div class="meta-value">${{data.changed_files}}</div>
                            </div>
                        </div>
                        ${{data.feature ? `<div class="pr-summary"><strong>Feature:</strong> ${{data.feature}}</div>` : ''}}
                        ${{data.pr_summary ? `<div class="pr-summary"><strong>PR Summary:</strong> ${{data.pr_summary}}</div>` : ''}}
                    </div>
                    
                    <div class="pr-content">
                        <h2 class="content-title">PR Description</h2>
                        <div class="pr-body">${{data.content || 'No description available'}}</div>
                    </div>
                    
                    ${{riskFactorsHtml}}
                    
                    <div class="files-section">
                        <h2 class="content-title">Files Changed (${{data.file_details ? data.file_details.length : 0}} files)</h2>
                        ${{filesHtml}}
                    </div>
                `;
            }}
            
            // Load PR details on page load
            document.addEventListener('DOMContentLoaded', loadPRDetails);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/pr-details")
async def get_pr_details(
    pr_id: int = Query(..., description="PR ID"),
    repo: str = Query(..., description="Repository name")
):
    """Get detailed PR information including file details"""
    if not milvus_collection:
        raise HTTPException(status_code=500, detail="Milvus collection not initialized")
    
    try:
        print(f"🔍 Fetching PR details for PR ID: {pr_id}, Repo: {repo}")
        
        # Get PR details from the PR collection
        query_expr = f'pr_id == {pr_id} and repo_name == "{repo}"'
        print(f"🔍 PR query expression: {query_expr}")
        
        pr_results = milvus_collection.query(
            expr=query_expr,
            output_fields=["pr_id", "pr_number", "title", "body", "author_name", "created_at", "merged_at", "status", "repo_name", "is_merged", "is_closed", "feature", "pr_summary", "risk_score", "risk_band", "risk_reasons", "additions", "deletions", "changed_files"],
            limit=1
        )
        
        print(f"🔍 PR query returned {len(pr_results) if pr_results else 0} results")
        
        if not pr_results:
            # Try to find any PRs with this ID to see if it exists
            try:
                test_results = milvus_collection.query(
                    expr=f'pr_id == {pr_id}',
                    output_fields=["pr_id", "repo_name"],
                    limit=5
                )
                if test_results:
                    available_repos = [r.get('repo_name', 'unknown') for r in test_results]
                    print(f"🔍 PR {pr_id} exists in repos: {available_repos}")
                    raise HTTPException(
                        status_code=404, 
                        detail=f"PR {pr_id} not found in repository '{repo}'. Available repositories: {', '.join(available_repos)}"
                    )
                else:
                    raise HTTPException(status_code=404, detail=f"PR {pr_id} not found in any repository")
            except Exception as test_error:
                print(f"🔍 Error testing PR existence: {test_error}")
                raise HTTPException(status_code=404, detail=f"PR {pr_id} not found")
        
        pr_data = pr_results[0]
        print(f"✅ Found PR: {pr_data.get('title', 'No title')} (PR #{pr_data.get('pr_number', 'N/A')})")
        
        # Get file details from the file collection
        file_collection_name = 'file_changes_what_the_repo'
        file_details = []
        
        try:
            if utility.has_collection(file_collection_name):
                print(f"🔍 File collection '{file_collection_name}' exists, loading...")
                file_collection = Collection(file_collection_name)
                file_collection.load()
                
                file_query_expr = f'pr_id == {pr_id} and repo_name == "{repo}"'
                print(f"🔍 File query expression: {file_query_expr}")
                
                file_results = file_collection.query(
                    expr=file_query_expr,
                    output_fields=["file_id", "file_status", "language", "additions", "deletions", "lines_changed", "ai_summary", "risk_score_file", "high_risk_flag"],
                    limit=100
                )
                
                file_details = file_results
                print(f"🔍 File query returned {len(file_details)} file records")
            else:
                print(f"⚠️ File collection '{file_collection_name}' does not exist")
        except Exception as file_error:
            print(f"⚠️ Error fetching file details: {file_error}")
            file_details = []
        
        # Format the response
        try:
            print(f"🔍 Processing PR data fields...")
            
            # Helper function to convert numpy types to Python native types
            def convert_numpy_types(value):
                """Convert numpy types to Python native types for JSON serialization"""
                import numpy as np
                if isinstance(value, np.integer):
                    return int(value)
                elif isinstance(value, np.floating):
                    return float(value)
                elif isinstance(value, np.ndarray):
                    return value.tolist()
                elif isinstance(value, np.bool_):
                    return bool(value)
                return value
            
            # Convert all values in pr_data to native Python types
            for key, value in pr_data.items():
                pr_data[key] = convert_numpy_types(value)
            
            # Handle risk_reasons - ensure it's a list, not a dict
            risk_reasons = pr_data.get('risk_reasons', [])
            print(f"🔍 Original risk_reasons type: {type(risk_reasons)}, value: {risk_reasons}")
            if isinstance(risk_reasons, dict):
                # If it's a dict, convert to list of values or empty list
                risk_reasons = list(risk_reasons.values()) if risk_reasons else []
                print(f"🔍 Converted risk_reasons from dict to list: {risk_reasons}")
            elif not isinstance(risk_reasons, list):
                risk_reasons = []
                print(f"🔍 Set risk_reasons to empty list (was {type(risk_reasons)})")
            
            # Handle file_details - ensure each file's risk_reasons is also a list
            processed_file_details = []
            print(f"🔍 Processing {len(file_details)} file details...")
            for i, file_detail in enumerate(file_details):
                print(f"🔍 Processing file {i+1}: {file_detail.get('file_id', 'unknown')}")
                try:
                    # Convert numpy types in file_detail
                    processed_file = {}
                    for key, value in file_detail.items():
                        processed_file[key] = convert_numpy_types(value)
                    
                    file_risk_reasons = processed_file.get('file_risk_reasons', [])
                    print(f"🔍 File {i+1} risk_reasons type: {type(file_risk_reasons)}, value: {file_risk_reasons}")
                    if isinstance(file_risk_reasons, dict):
                        file_risk_reasons = list(file_risk_reasons.values()) if file_risk_reasons else []
                        print(f"🔍 File {i+1} converted risk_reasons from dict to list: {file_risk_reasons}")
                    elif not isinstance(file_risk_reasons, list):
                        file_risk_reasons = []
                        print(f"🔍 File {i+1} set risk_reasons to empty list (was {type(file_risk_reasons)})")
                    processed_file['file_risk_reasons'] = file_risk_reasons
                    processed_file_details.append(processed_file)
                except Exception as file_error:
                    print(f"❌ Error processing file {i+1}: {file_error}")
                    # Add a safe version of the file detail
                    safe_file = {
                        'file_id': convert_numpy_types(file_detail.get('file_id', 'unknown')),
                        'file_status': convert_numpy_types(file_detail.get('file_status', '')),
                        'language': convert_numpy_types(file_detail.get('language', '')),
                        'additions': convert_numpy_types(file_detail.get('additions', 0)),
                        'deletions': convert_numpy_types(file_detail.get('deletions', 0)),
                        'lines_changed': convert_numpy_types(file_detail.get('lines_changed', 0)),
                        'ai_summary': convert_numpy_types(file_detail.get('ai_summary', '')),
                        'risk_score_file': convert_numpy_types(file_detail.get('risk_score_file', 0.0)),
                        'high_risk_flag': convert_numpy_types(file_detail.get('high_risk_flag', False)),
                        'file_risk_reasons': []
                    }
                    processed_file_details.append(safe_file)
            
            print(f"🔍 Building response data...")
            
            # Build response data step by step to identify the problematic field
            response_data = {}
            
            # Add fields one by one with error checking
            try:
                response_data["pr_id"] = pr_data.get('pr_id', 0)
                print(f"✅ Added pr_id: {response_data['pr_id']}")
            except Exception as e:
                print(f"❌ Error adding pr_id: {e}")
                response_data["pr_id"] = 0
                
            try:
                response_data["pr_number"] = pr_data.get('pr_number', 0)
                print(f"✅ Added pr_number: {response_data['pr_number']}")
            except Exception as e:
                print(f"❌ Error adding pr_number: {e}")
                response_data["pr_number"] = 0
                
            try:
                response_data["title"] = pr_data.get('title', '') or ''
                print(f"✅ Added title: {response_data['title'][:50]}...")
            except Exception as e:
                print(f"❌ Error adding title: {e}")
                response_data["title"] = ''
                
            try:
                response_data["content"] = pr_data.get('body', '') or ''
                print(f"✅ Added content: {len(response_data['content'])} chars")
            except Exception as e:
                print(f"❌ Error adding content: {e}")
                response_data["content"] = ''
                
            try:
                response_data["author"] = pr_data.get('author_name', '') or ''
                print(f"✅ Added author: {response_data['author']}")
            except Exception as e:
                print(f"❌ Error adding author: {e}")
                response_data["author"] = ''
                
            try:
                response_data["created_at"] = pr_data.get('created_at', 0) or 0
                print(f"✅ Added created_at: {response_data['created_at']}")
            except Exception as e:
                print(f"❌ Error adding created_at: {e}")
                response_data["created_at"] = 0
                
            try:
                response_data["merged_at"] = pr_data.get('merged_at', 0) or 0
                print(f"✅ Added merged_at: {response_data['merged_at']}")
            except Exception as e:
                print(f"❌ Error adding merged_at: {e}")
                response_data["merged_at"] = 0
                
            try:
                response_data["status"] = pr_data.get('status', '') or ''
                print(f"✅ Added status: {response_data['status']}")
            except Exception as e:
                print(f"❌ Error adding status: {e}")
                response_data["status"] = ''
                
            try:
                response_data["is_merged"] = pr_data.get('is_merged', False) or False
                print(f"✅ Added is_merged: {response_data['is_merged']}")
            except Exception as e:
                print(f"❌ Error adding is_merged: {e}")
                response_data["is_merged"] = False
                
            try:
                response_data["is_closed"] = pr_data.get('is_closed', False) or False
                print(f"✅ Added is_closed: {response_data['is_closed']}")
            except Exception as e:
                print(f"❌ Error adding is_closed: {e}")
                response_data["is_closed"] = False
                
            try:
                response_data["feature"] = pr_data.get('feature', '') or ''
                print(f"✅ Added feature: {response_data['feature']}")
            except Exception as e:
                print(f"❌ Error adding feature: {e}")
                response_data["feature"] = ''
                
            try:
                response_data["pr_summary"] = pr_data.get('pr_summary', '') or ''
                print(f"✅ Added pr_summary: {len(response_data['pr_summary'])} chars")
            except Exception as e:
                print(f"❌ Error adding pr_summary: {e}")
                response_data["pr_summary"] = ''
                
            try:
                response_data["risk_score"] = float(pr_data.get('risk_score', 0.0) or 0.0)
                print(f"✅ Added risk_score: {response_data['risk_score']}")
            except Exception as e:
                print(f"❌ Error adding risk_score: {e}")
                response_data["risk_score"] = 0.0
                
            try:
                response_data["risk_band"] = pr_data.get('risk_band', 'low') or 'low'
                print(f"✅ Added risk_band: {response_data['risk_band']}")
            except Exception as e:
                print(f"❌ Error adding risk_band: {e}")
                response_data["risk_band"] = 'low'
                
            try:
                response_data["risk_reasons"] = risk_reasons
                print(f"✅ Added risk_reasons: {len(response_data['risk_reasons'])} items")
            except Exception as e:
                print(f"❌ Error adding risk_reasons: {e}")
                response_data["risk_reasons"] = []
                
            try:
                response_data["additions"] = pr_data.get('additions', 0) or 0
                print(f"✅ Added additions: {response_data['additions']}")
            except Exception as e:
                print(f"❌ Error adding additions: {e}")
                response_data["additions"] = 0
                
            try:
                response_data["deletions"] = pr_data.get('deletions', 0) or 0
                print(f"✅ Added deletions: {response_data['deletions']}")
            except Exception as e:
                print(f"❌ Error adding deletions: {e}")
                response_data["deletions"] = 0
                
            try:
                response_data["changed_files"] = pr_data.get('changed_files', 0) or 0
                print(f"✅ Added changed_files: {response_data['changed_files']}")
            except Exception as e:
                print(f"❌ Error adding changed_files: {e}")
                response_data["changed_files"] = 0
                
            try:
                response_data["file_details"] = processed_file_details
                print(f"✅ Added file_details: {len(response_data['file_details'])} files")
            except Exception as e:
                print(f"❌ Error adding file_details: {e}")
                response_data["file_details"] = []
            
            print(f"✅ Successfully formatted response for PR {pr_id}")
            return response_data
            
        except Exception as format_error:
            print(f"❌ Error formatting response: {format_error}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Error formatting PR details: {str(format_error)}")
        
    except Exception as e:
        print(f"❌ Error fetching PR details: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PR details: {str(e)}")

@app.get("/api/example-queries")
async def get_example_queries(repo: str = Query(None, description="Selected repository")):
    """Get example queries for a specific repository"""
    if not repo:
        raise HTTPException(status_code=400, detail="Repository name is required for example queries")

    try:
        # In a real application, you might fetch these from a database or a config file
        # For now, we'll return a few generic ones or ones specific to the repo if available
        example_queries = [
            {"query": "What was shipped in the last two weeks?", "type": "Time-based", "description": "Find PRs merged in the last 14 days with features and improvements.", "tags": ["time", "last_two_weeks", "shipped"]},
            {"query": "Show me high risk code changes", "type": "Risk-based", "description": "Find code changes with high risk scores and potential issues.", "tags": ["risk", "high_risk", "code"]},
            {"query": "What are the most recent features?", "type": "Feature-based", "description": "Find recent PRs that represent new features or enhancements.", "tags": ["feature", "recent", "enhancement"]},
            {"query": "Find changes by author john_doe", "type": "Author-based", "description": "Search for code changes authored by a specific user.", "tags": ["author", "john_doe"]},
            {"query": "Show me all merged changes from this year", "type": "Status-based", "description": "List all merged PRs from the current year.", "tags": ["status", "merged", "this_year"]},
            {"query": "What files were changed recently?", "type": "File-based", "description": "Get detailed file information for recent changes.", "tags": ["files", "recent", "details"]},
            {"query": "Find database schema changes", "type": "Code-based", "description": "Search for changes related to database schemas and migrations.", "tags": ["database", "schema", "migration"]},
            {"query": "Show me API changes", "type": "Code-based", "description": "Find changes related to API endpoints and interfaces.", "tags": ["api", "endpoints", "interface"]}
        ]

        # If a specific repo is requested, we can filter or return more repo-specific examples
        if repo:
            # For demonstration, we'll return a subset of the generic ones
            repo_specific_examples = [
                {"query": f"What was shipped in {repo} last week?", "type": "Time-based", "description": f"Find PRs shipped in {repo} last 7 days.", "tags": ["time", "last_week", repo]},
                {"query": f"Find PRs by author John Doe in {repo}", "type": "Author-based", "description": f"Search for PRs authored by a specific user in {repo}.", "tags": ["author", "john_doe", repo]},
                {"query": f"What are the top 5 riskiest PRs in {repo}?", "type": "Risk-based", "description": f"Identify PRs with the highest risk scores in {repo}.", "tags": ["risk", "top_risk", repo]},
                {"query": f"Show me all merged PRs from last month in {repo}", "type": "Status-based", "description": f"List all merged PRs from the last 30 days in {repo}.", "tags": ["status", "merged", "last_month", repo]},
                {"query": f"What are the most recent PRs in {repo}?", "type": "Recent-based", "description": f"Find the latest PRs in {repo}.", "tags": ["recent", "latest", repo]}
            ]
            example_queries = repo_specific_examples

        return {"queries": example_queries}
    except Exception as e:
        print(f"Error fetching example queries: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch example queries: {e}")

@app.get("/api/engineers")
async def get_engineers(repo: str = Query(..., description="Repository name")):
    """Get list of engineers for a repository"""
    if not engineer_lens_ui:
        raise HTTPException(status_code=500, detail="Engineer Lens UI not initialized")
    
    try:
        engineers = engineer_lens_ui.get_engineers_for_repo(repo)
        return engineers
    except Exception as e:
        print(f"Error fetching engineers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch engineers: {str(e)}")

@app.get("/api/engineer-metrics")
async def get_engineer_metrics(
    username: str = Query(..., description="Engineer username"),
    repo: str = Query(..., description="Repository name"),
    window_days: int = Query(30, description="Time window in days")
):
    """Get metrics for a specific engineer"""
    if not engineer_lens_ui:
        raise HTTPException(status_code=500, detail="Engineer Lens UI not initialized")
    
    try:
        metrics = engineer_lens_ui.get_engineer_metrics(username, repo, window_days)
        return metrics
    except Exception as e:
        print(f"Error fetching engineer metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch engineer metrics: {str(e)}")

@app.get("/api/what-shipped-data")
async def get_what_shipped_data(
    repo: str = Query(..., description="Repository name"),
    time_window: str = Query("30d", description="Time window (7d, 30d, 90d, all)"),
    author: str = Query(None, description="Filter by author"),
    risk_level: str = Query(None, description="Filter by risk level (low, medium, high)"),
    feature_only: bool = Query(False, description="Show only features"),
    limit: int = Query(50, description="Number of results to return")
):
    """Get What Shipped data from repo_prs table"""
    try:
        # Initialize Supabase client
        try:
            supabase_client = create_supabase_client()
        except ValueError as e:
            raise HTTPException(status_code=500, detail="Supabase configuration not found")
        
        # Build query
        query = supabase_client.table('repo_prs').select('*').eq('repo_name', repo)
        
        # Apply time filter
        if time_window != "all":
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            if time_window in days_map:
                days_ago = datetime.now() - timedelta(days=days_map[time_window])
                query = query.gte('merged_at', days_ago.isoformat())
        
        # Apply author filter
        if author:
            query = query.eq('author', author)
        
        # Apply risk level filter
        if risk_level:
            if risk_level == "high":
                query = query.eq('high_risk', True)
            elif risk_level == "medium":
                query = query.eq('high_risk', False).gte('risk_score', 4.0)
            elif risk_level == "low":
                query = query.lt('risk_score', 4.0)
        
        # Apply feature filter
        if feature_only:
            query = query.neq('feature_rule', 'excluded')
        
        # Order by merged_at desc and limit
        query = query.order('merged_at', desc=True).limit(limit)
        
        # Execute query
        result = query.execute()
        
        return {
            "data": result.data,
            "total": len(result.data),
            "filters": {
                "repo": repo,
                "time_window": time_window,
                "author": author,
                "risk_level": risk_level,
                "feature_only": feature_only
            }
        }
        
    except Exception as e:
        print(f"Error fetching What Shipped data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch What Shipped data: {e}")

@app.get("/api/what-shipped-summary")
async def get_what_shipped_summary(
    repo: str = Query(..., description="Repository name"),
    time_window: str = Query("30d", description="Time window (7d, 30d, 90d, all)")
):
    """Get summary statistics for What Shipped page"""
    try:
        # Initialize Supabase client
        try:
            supabase_client = create_supabase_client()
        except ValueError as e:
            raise HTTPException(status_code=500, detail="Supabase configuration not found")
        
        # Build base query
        query = supabase_client.table('repo_prs').select('*').eq('repo_name', repo)
        
        # Apply time filter
        if time_window != "all":
            days_map = {"7d": 7, "30d": 30, "90d": 90}
            if time_window in days_map:
                days_ago = datetime.now() - timedelta(days=days_map[time_window])
                query = query.gte('merged_at', days_ago.isoformat())
        
        # Get all data for summary
        result = query.execute()
        data = result.data
        
        if not data:
            return {
                "total_prs": 0,
                "features": 0,
                "high_risk": 0,
                "merged": 0,
                "top_authors": [],
                "risk_distribution": {"low": 0, "medium": 0, "high": 0},
                "feature_distribution": {"features": 0, "non_features": 0}
            }
        
        # Calculate summary statistics
        total_prs = len(data)
        features = sum(1 for pr in data if pr.get('feature_rule') != 'excluded')
        high_risk = sum(1 for pr in data if pr.get('high_risk', False))
        merged = sum(1 for pr in data if pr.get('is_merged', False))
        
        # Top authors
        author_counts = {}
        for pr in data:
            author = pr.get('author', 'Unknown')
            author_counts[author] = author_counts.get(author, 0) + 1
        
        top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Risk distribution
        risk_distribution = {"low": 0, "medium": 0, "high": 0}
        for pr in data:
            risk_score = pr.get('risk_score', 0)
            if risk_score >= 7.0:
                risk_distribution["high"] += 1
            elif risk_score >= 4.0:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["low"] += 1
        
        # Feature distribution
        feature_distribution = {"features": features, "non_features": total_prs - features}
        
        return {
            "total_prs": total_prs,
            "features": features,
            "high_risk": high_risk,
            "merged": merged,
            "top_authors": [{"author": author, "count": count} for author, count in top_authors],
            "risk_distribution": risk_distribution,
            "feature_distribution": feature_distribution
        }
        
    except Exception as e:
        print(f"Error fetching What Shipped summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch What Shipped summary: {e}")

@app.get("/api/what-shipped-authors")
async def get_what_shipped_authors(
    repo: str = Query(..., description="Repository name")
):
    """Get list of authors for What Shipped page"""
    try:
        # Initialize Supabase client
        try:
            supabase_client = create_supabase_client()
        except ValueError as e:
            raise HTTPException(status_code=500, detail="Supabase configuration not found")
        
        # Try to get authors from the authors table first
        try:
            response = supabase_client.table('authors').select('*').execute()
            authors = response.data
            
            # Filter authors who have PRs in this repo
            repo_authors = []
            for author in authors:
                # Check if author has any PRs in this repo
                prs_response = supabase_client.table('repo_prs').select('author').eq('repo_name', repo).eq('author', author['username']).limit(1).execute()
                if prs_response.data:
                    repo_authors.append(author)
            
            # Sort by username
            repo_authors.sort(key=lambda x: x['username'])
            
            if repo_authors:
                return {
                    "authors": repo_authors,
                    "total": len(repo_authors)
                }
        except Exception as e:
            print(f"Warning: Could not access authors table: {e}")
        
        # Fallback: Get authors directly from repo_prs table
        print(f"Using fallback method to get authors from repo_prs table for {repo}")
        
        # Get unique authors from repo_prs table for this repository
        response = supabase_client.table('repo_prs').select('author').eq('repo_name', repo).execute()
        
        # Extract unique authors
        unique_authors = list(set(pr.get('author') for pr in response.data if pr.get('author')))
        unique_authors.sort()
        
        # Convert to the same format as authors table
        authors_list = [{"username": author} for author in unique_authors]
        
        return {
            "authors": authors_list,
            "total": len(authors_list)
        }
        
    except Exception as e:
        print(f"Error fetching What Shipped authors: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch What Shipped authors: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "milvus_connected": milvus_collection is not None}

if __name__ == "__main__":
    # Load environment variables
    required_env_vars = ['MILVUS_URL', 'MILVUS_TOKEN', 'OPENAI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        exit(1)
    
    print("Starting What the repo-gpt...")
    print("Environment variables configured successfully")
    
    # Initialize connections
    initialize_connections()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )