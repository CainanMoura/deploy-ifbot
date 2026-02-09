import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv('GROQ_API_KEY'))

try:
    modelos = client.models.list()
    print(f"Total de modelos: {len(modelos.data)}")
    print("\nModelos disponíveis:")
    for i, modelo in enumerate(modelos.data[:20]):
        print(f"{i+1:2}. {modelo.id}")
        
    print(f"\nModelo 1: {modelos.data[0].id}")
    print(f"Modelo 2: {modelos.data[1].id}")
    print(f"Modelo 3: {modelos.data[2].id}")
    
except Exception as e:
    print(f"Erro: {e}")