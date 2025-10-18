# main_experiment.py (Final version with rate limiting)

import json
import dspy
from config import OPENAI_API_KEY
import llama_index.core as lci
from llama_index.core import Settings, load_index_from_storage, StorageContext
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from collections import Counter
import time # <--- IMPORT THE TIME MODULE

# --- 1. CONFIGURE DSPY ---
print("Configuring DSPy settings...")
llm = dspy.OpenAI(model='gpt-3.5-turbo', max_tokens=400, api_key=OPENAI_API_KEY, temperature=0.7)

from dspy.retrieve.retrieve import Retrieve

print("Configuring local embedding model for retrieval...")
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
try:
    index = load_index_from_storage(StorageContext.from_defaults(persist_dir="./index_storage"))
except FileNotFoundError:
    print("Index not found. Please run 'python build_index.py' first.")
    exit()

llama_index_retriever = index.as_retriever(similarity_top_k=3)

class RAG_from_LlamaIndex(dspy.Retrieve):
    def __init__(self, llama_index_retriever, k=3):
        super().__init__(k=k)
        self.llama_index_retriever = llama_index_retriever
    def forward(self, query_or_queries, **kwargs):
        queries = [query_or_queries] if isinstance(query_or_queries, str) else query_or_queries
        retrieved_docs = []
        for query in queries:
            nodes = self.llama_index_retriever.retrieve(query)
            for node in nodes:
                retrieved_docs.append(dspy.Prediction(long_text=node.get_content()))
        return retrieved_docs

retriever_model = RAG_from_LlamaIndex(llama_index_retriever, k=3)
dspy.settings.configure(lm=llm, rm=retriever_model)
print("DSPy configuration complete.")


# --- 2. DEFINE THE TASK SIGNATURE ---
class MedicalFR(dspy.Signature):
    """Extracts a single, precise functional requirement from a medical conversation, informed by relevant context."""
    context = dspy.InputField(desc="Relevant medical guidelines or rules.")
    utterances = dspy.InputField(desc="A dialogue between medical professionals or a patient.")
    functional_requirement = dspy.OutputField(desc="A formal requirement starting with 'The system shall...'.")


# --- 3. CREATE THE DSPY MODULES (PE Techniques) ---
class ZeroShotFR(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retriever = dspy.Retrieve(k=3)
        self.generate_fr = dspy.Predict(MedicalFR)
    def forward(self, utterances):
        conversation_string = "\n".join(utterances)
        context = self.retriever(conversation_string).passages
        return self.generate_fr(context=context, utterances=conversation_string)

class CoTFR(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retriever = dspy.Retrieve(k=3)
        self.generate_fr = dspy.ChainOfThought(MedicalFR)
    def forward(self, utterances):
        conversation_string = "\n".join(utterances)
        context = self.retriever(conversation_string).passages
        return self.generate_fr(context=context, utterances=conversation_string)

class SelfConsistencyFR(dspy.Module):
    def __init__(self, num_chains=3):
        super().__init__()
        self.generate_chains = dspy.ChainOfThought(MedicalFR)
        self.num_chains = num_chains
    def forward(self, utterances):
        completions = self.generate_chains(utterances=utterances, n=self.num_chains)
        answers = [c.functional_requirement for c in completions]
        most_common_answer = Counter(answers).most_common(1)[0][0]
        return dspy.Prediction(functional_requirement=most_common_answer)


# --- 4. LOAD DATA AND RUN THE EXPERIMENT ---
def run_qualitative_experiment():
    print("\n--- Starting Qualitative Experiment ---")
    
    with open('./data/english-test.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    testset = [dspy.Example(**x).with_inputs('utterances') for x in test_data]
    print(f"Loaded {len(testset)} testing examples.")

    zero_shot_model = ZeroShotFR()
    cot_model = CoTFR()
    # self_consistency_model = SelfConsistencyFR() # <-- TEMPORARILY COMMENT THIS OUT

    for i, example in enumerate(testset[:5]):
        print(f"\n--- Example {i+1} ---")
        
        zero_shot_pred = zero_shot_model(utterances=example.utterances)
        cot_pred = cot_model(utterances=example.utterances)
        # self_consistency_pred = self_consistency_model(utterances=example.utterances) # <-- TEMPORARILY COMMENT THIS OUT
        
        print(f"Conversation: {' '.join(example.utterances)}\n")
        print(f"ZeroShot Output:         {zero_shot_pred.functional_requirement}")
        print(f"CoT Output:              {cot_pred.functional_requirement}")
        # print(f"Self-Consistency Output: {self_consistency_pred.functional_requirement}") # <-- TEMPORARILY COMMENT THIS OUT

        # We can keep the sleep here, it's good practice
        print("\nPausing for 20 seconds...")
        time.sleep(20)

    print("\n--- Qualitative Experiment Finished ---")
    print("Inspect the outputs above to compare the models.")


if __name__ == "__main__":
    run_qualitative_experiment()