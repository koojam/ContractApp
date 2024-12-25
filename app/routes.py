from flask import Blueprint, render_template, jsonify, request, current_app, send_file, redirect, url_for, send_from_directory
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.docstore.document import Document
import os
import mimetypes
from app.config_manager import ConfigManager
from typing import List, Dict
import re
from langchain.prompts import PromptTemplate

main = Blueprint('main', __name__)

# Initialize the QA chain
qa_chain = None

def initialize_document_chain():
    """Initialize the document processing and QA chain"""
    print("\n=== Initializing Document Chain ===")
    
    contracts_dir = current_app.config['CONTRACTS_DIR']
    print(f"Looking for contracts in: {contracts_dir}")
    
    if not os.path.exists(contracts_dir):
        print(f"Error: Contracts directory does not exist: {contracts_dir}")
        return None
    
    documents = []
    file_count = 0
    
    # Process each file based on its type
    for root, _, files in os.walk(contracts_dir):
        print(f"\nScanning directory: {root}")
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        print(f"Found PDF files: {pdf_files}")
        file_count = len(pdf_files)
        
        for file in pdf_files:
            file_path = os.path.join(root, file)
            try:
                print(f"\nLoading PDF file: {file}")
                loader = PyMuPDFLoader(file_path)
                docs = loader.load()
                print(f"Loaded {len(docs)} pages from {file}")
                for doc in docs:
                    doc.metadata['title'] = file  # Add file name to metadata
                documents.extend(docs)
                print(f"Successfully loaded PDF: {file}")
            except Exception as e:
                print(f"Error loading {file}: {str(e)}")
    
    if not documents:
        print("No documents were loaded!")
        return None
        
    print(f"\nTotal files found: {file_count}")
    print(f"Total documents loaded: {len(documents)}")
    
    try:
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        splits = text_splitter.split_documents(documents)
        print(f"Split into {len(splits)} chunks")
        
        if not splits:
            print("No text chunks were created!")
            return None
        
        # Create embeddings and vector store
        print("Creating embeddings...")
        embeddings = OpenAIEmbeddings()
        vectorstore = Chroma.from_documents(splits, embeddings)
        
        # Create QA chain with specific prompt
        print("Creating QA chain...")
        llm = ChatOpenAI(temperature=0, model_name="gpt-4")
        
        # Create the chain with a specific prompt
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm,
            vectorstore.as_retriever(search_kwargs={"k": 10}),  # Increase number of retrieved documents
            return_source_documents=True,
            verbose=True,
            combine_docs_chain_kwargs={
                "prompt": PromptTemplate(
                    template="""You are a helpful contract analysis assistant. Answer the question based strictly on the provided context.
                    For questions about dates or expirations, only include contracts that exactly match the specified time period.
                    Be precise and accurate with dates.
                    
                    When asked for tabular format:
                    1. Use | to separate columns
                    2. Include a header row
                    3. Align data properly in columns
                    4. For expiration summaries, group by year and show count
                    
                    For statistical summaries:
                    1. Group and count items appropriately
                    2. Present data in a clear, organized manner
                    3. Include totals when relevant
                    
                    Question: {question}
                    Context: {context}
                    
                    Answer: """,
                    input_variables=["question", "context"]
                )
            }
        )
        
        print("Document chain initialization complete!")
        return qa_chain
        
    except Exception as e:
        print(f"Error in chain initialization: {str(e)}")
        return None

def format_table_response(answer: str) -> str:
    """Format the response as an HTML table if it contains tabular data"""
    if '|' not in answer:
        return answer
        
    lines = answer.strip().split('\n')
    html = ['<table class="comparison-table">']
    
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        if i == 0:  # Header row
            html.append('<thead><tr>')
            html.extend(f'<th>{cell}</th>' for cell in cells)
            html.append('</tr></thead><tbody>')
        else:  # Data rows
            html.append('<tr>')
            html.extend(f'<td>{cell}</td>' for cell in cells)
            html.append('</tr>')
    
    html.append('</tbody></table>')
    return '\n'.join(html)

def extract_company_names(contracts_dir: str) -> set:
    """Dynamically extract company names from contract filenames"""
    company_names = set()
    
    # Common words to exclude
    common_words = {'inc', 'ltd', 'llc', 'partnership', 'agreement', 'contract', 'nda', 'non', 'disclosure'}
    
    for filename in os.listdir(contracts_dir):
        if filename.lower().endswith('.pdf'):
            # Split filename into words and remove extension
            words = filename.replace('.pdf', '').split()
            
            # Process words to extract potential company names
            current_company = []
            for word in words:
                word_lower = word.lower()
                # Skip common words and keep meaningful parts
                if word_lower not in common_words:
                    current_company.append(word)
                elif current_company:  # If we have collected some company words
                    company_name = ' '.join(current_company).lower()
                    if company_name:
                        company_names.add(company_name)
                    current_company = []
            
            # Add any remaining company words
            if current_company:
                company_name = ' '.join(current_company).lower()
                if company_name:
                    company_names.add(company_name)
    
    print(f"Extracted company names: {company_names}")
    return company_names

def filter_relevant_sources(sources: List[Dict], question: str, answer: str) -> List[Dict]:
    """Filter sources to only include documents mentioned in the answer"""
    relevant_sources = []
    seen_sources = set()
    
    # Convert answer to lowercase for case-insensitive matching
    answer_lower = answer.lower()
    
    # For questions about total number of contracts, include all sources
    if any(phrase in question.lower() for phrase in ['how many contracts', 'what contracts']):
        return sources
    
    for source in sources:
        file_name = source['file']
        file_lower = file_name.lower()
        
        # Extract company names and other identifiers from filename
        words = file_lower.replace('.pdf', '').split()
        identifiers = []
        
        # Build phrase from consecutive words
        current_phrase = []
        for word in words:
            if word not in {'inc', 'ltd', 'llc', 'partnership', 'agreement', 
                          'contract', 'nda', 'non', 'disclosure'}:
                current_phrase.append(word)
            elif current_phrase:
                identifiers.append(' '.join(current_phrase))
                current_phrase = []
        
        if current_phrase:
            identifiers.append(' '.join(current_phrase))
        
        # Check if any identifier from the filename appears in the answer
        is_relevant = any(identifier.lower() in answer_lower for identifier in identifiers)
        
        if is_relevant and file_lower not in seen_sources:
            seen_sources.add(file_lower)
            relevant_sources.append(source)
            print(f"Including relevant source: {file_name} (matched in answer)")
    
    # If the answer mentions all contracts, return all sources
    if len(relevant_sources) == 0 and any(phrase in answer_lower for phrase in 
            ['all contracts', 'following contracts', 'have these contracts']):
        return sources
    
    print(f"Filtered from {len(sources)} to {len(relevant_sources)} relevant sources")
    return relevant_sources

@main.route('/')
def home():
    config_manager = ConfigManager()
    print("Checking setup status...")
    print(f"Contracts directory: {config_manager.get_contracts_dir()}")
    print(f"Setup complete: {config_manager.is_setup_complete()}")
    if not config_manager.is_setup_complete():
        print("Showing setup page")
        return render_template('setup.html')
    print("Showing main page")
    return render_template('index.html')

@main.route('/view_contract/<path:filename>')
def view_contract(filename):
    """Serve contract files"""
    try:
        contracts_dir = current_app.config['CONTRACTS_DIR']
        file_path = os.path.join(contracts_dir, filename)
        
        # Get the file's MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # For PDFs and other documents, serve with correct MIME type
        return send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        return f"Error accessing file: {str(e)}", 404

@main.route('/ask', methods=['POST'])
def ask():
    global qa_chain
    
    try:
        print("\n=== Processing Question ===")
        data = request.get_json()
        question = data.get('query', '').strip()
        print(f"Question received: {question}")
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
            
        # Get actual file count
        contracts_dir = current_app.config['CONTRACTS_DIR']
        actual_file_count = sum(1 for f in os.listdir(contracts_dir) if f.lower().endswith('.pdf'))
        print(f"Actual number of PDF files: {actual_file_count}")
        
        # If asking about number of contracts, return direct count
        if any(phrase in question.lower() for phrase in ['how many', 'number of']):
            answer = f"You have {actual_file_count} contracts in your folder."
            sources = []
            for file in os.listdir(contracts_dir):
                if file.lower().endswith('.pdf'):
                    sources.append({
                        'file': file,
                        'url': f'/view_contract/{file}',
                        'page': 'N/A'
                    })
            return jsonify({
                'message': answer,
                'sources': sources
            })
        
        # For other questions, use the QA chain
        if qa_chain is None:
            print("Initializing QA chain...")
            qa_chain = initialize_document_chain()
            if qa_chain is None:
                return jsonify({'error': 'Failed to initialize QA chain. No documents found.'}), 500
        
        # Get response from QA chain
        print("Getting response from QA chain...")
        result = qa_chain({"question": question, "chat_history": []})
        
        # Format response with source documents
        answer = result.get('answer', '')
        print(f"Raw answer: {answer}")
        
        # Format as table if needed
        formatted_answer = format_table_response(answer)
        print(f"Formatted answer: {formatted_answer}")
        
        # Process and filter sources
        sources = []
        seen_paths = set()  # Track unique file paths
        
        if 'source_documents' in result:
            print("Processing source documents...")
            for doc in result['source_documents']:
                try:
                    abs_path = doc.metadata.get('source', 'Unknown')
                    rel_path = os.path.relpath(abs_path, current_app.config['CONTRACTS_DIR'])
                    
                    # Only add if we haven't seen this path before
                    if rel_path not in seen_paths:
                        seen_paths.add(rel_path)
                        source = {
                            'file': rel_path,
                            'url': f'/view_contract/{rel_path}',
                            'page': doc.metadata.get('page', 'N/A')
                        }
                        sources.append(source)
                        print(f"Added source: {rel_path}")
                except Exception as e:
                    print(f"Error processing source document: {str(e)}")
        
        # Filter sources to only include relevant documents
        filtered_sources = filter_relevant_sources(sources, question, answer)
        print(f"Filtered sources: {filtered_sources}")
        
        return jsonify({
            'message': formatted_answer,
            'sources': filtered_sources
        })
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@main.route('/settings/info')
def settings_info():
    """Get current settings information"""
    try:
        config_manager = ConfigManager()
        contracts_dir = config_manager.get_contracts_dir()
        
        # Count documents in the directory
        doc_count = 0
        if os.path.exists(contracts_dir):
            for root, _, files in os.walk(contracts_dir):
                doc_count += sum(1 for f in files if f.lower().endswith(('.pdf', '.txt')))
        
        return jsonify({
            'contracts_dir': contracts_dir,
            'doc_count': doc_count
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/settings/change_folder', methods=['POST'])
def change_folder():
    """Change the contracts folder"""
    try:
        # Note: In the desktop app, this will be handled by the Qt file dialog
        # This route will be called after the folder is selected
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/settings/reload_docs', methods=['POST'])
def reload_docs():
    """Reload all documents"""
    try:
        global qa_chain
        qa_chain = None  # Force reinitialization
        qa_chain = initialize_document_chain()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/dashboard/stats')
def get_dashboard_stats():
    """Get statistics for the dashboard"""
    try:
        contracts_dir = current_app.config['CONTRACTS_DIR']
        stats = {
            'total_contracts': 0,
            'contract_types': {},
            'active_vs_expiring': {
                'Active': 0,
                'Expiring Soon': 0
            },
            'expiration_timeline': []
        }
        
        # Initialize QA chain if needed
        global qa_chain
        if qa_chain is None:
            qa_chain = initialize_document_chain()
        
        # Get contract information using QA chain
        result = qa_chain({
            "question": """List all contracts with their expiration dates in a table format. 
                          Include header row and use | as separator.
                          Format: Contract Name | Expiration Date
                          For each contract, show exact expiration date in format: Month DD, YYYY
                          Example format:
                          Contract Name | Expiration Date
                          ABC Contract | January 15, 2025""",
            "chat_history": []
        })
        
        from datetime import datetime, timedelta
        current_date = datetime.now()
        expiring_soon_threshold = current_date + timedelta(days=30)  # 30 days threshold
        
        # Add debug print statements
        print("\n=== Processing Contract Dates ===")
        
        # Process the answer to extract dates
        answer = result.get('answer', '')
        print(f"Raw answer from QA: {answer}")
        
        for line in answer.split('\n'):
            if '|' in line:  # Table format
                parts = [part.strip() for part in line.split('|')]
                print(f"Processing line: {parts}")
                if len(parts) >= 2:
                    try:
                        # Extract and parse the date
                        contract_name = parts[0].strip()
                        date_str = parts[1].strip()
                        print(f"Attempting to parse date: {date_str} for contract: {contract_name}")
                        
                        expiry_date = datetime.strptime(date_str, '%B %d, %Y')
                        print(f"Successfully parsed date: {expiry_date}")
                        
                        # Classify as Active or Expiring Soon
                        if expiry_date > current_date:
                            if expiry_date <= expiring_soon_threshold:
                                stats['active_vs_expiring']['Expiring Soon'] += 1
                            else:
                                stats['active_vs_expiring']['Active'] += 1
                            
                            # Add to timeline
                            timeline_entry = {
                                'contract': contract_name,
                                'date': date_str,
                                'timestamp': expiry_date.timestamp()
                            }
                            stats['expiration_timeline'].append(timeline_entry)
                            print(f"Added to timeline: {timeline_entry}")
                            
                    except (ValueError, IndexError) as e:
                        print(f"Error processing date: {e}")
                        continue
        
        print(f"\nFinal timeline data: {stats['expiration_timeline']}")
        
        # Sort timeline by date
        stats['expiration_timeline'].sort(key=lambda x: x['timestamp'])
        
        # Count total contracts
        stats['total_contracts'] = sum(1 for f in os.listdir(contracts_dir) 
                                     if f.lower().endswith('.pdf'))
        
        # Process contract types
        for filename in os.listdir(contracts_dir):
            if filename.lower().endswith('.pdf'):
                contract_type = 'Other'
                if 'partnership' in filename.lower():
                    contract_type = 'Partnership Agreement'
                elif 'nda' in filename.lower() or 'disclosure' in filename.lower():
                    contract_type = 'Non-Disclosure Agreement'
                
                stats['contract_types'][contract_type] = stats['contract_types'].get(contract_type, 0) + 1
        
        return jsonify(stats)
    except Exception as e:
        print(f"Error getting dashboard stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)