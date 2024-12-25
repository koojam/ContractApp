from app import create_app

app = create_app()

if __name__ == '__main__':
    print("\n=== Starting Contract Assistant ===")
    print(f"Visit: http://localhost:8001")
    app.run(host='localhost', port=8001, debug=True) 