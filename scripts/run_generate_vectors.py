# scripts/run_generate_vectors.py
from app.services.vector_generator import run_batch_generation

if __name__ == "__main__":
    run_batch_generation(batch_size=30, max_rounds=20)