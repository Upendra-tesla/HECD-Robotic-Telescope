#!/usr/bin/env python3
"""
Benchmark Manager - Tests models and saves results with FULL responses
"""

import os
import json
import time
import requests
import statistics
from datetime import datetime
from typing import Dict, List
from collections import defaultdict
from PyQt5.QtCore import QThread, pyqtSignal

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELS_TO_TEST = ["qwen2.5:1.5b", "deepseek-r1:1.5b", "tinyllama:latest"]

# 100 Test Questions
BENCHMARK_QUESTIONS = [
    {"id": 1, "category": "astronomy", "complexity": "high", "question": "What is a black hole and how does it form?"},
    {"id": 2, "category": "astronomy", "complexity": "high", "question": "Explain the life cycle of a star from birth to death"},
    {"id": 3, "category": "astronomy", "complexity": "medium", "question": "What are the differences between a meteor, meteorite, and meteoroid?"},
    {"id": 4, "category": "astronomy", "complexity": "low", "question": "How far away is the Andromeda Galaxy from Earth?"},
    {"id": 5, "category": "astronomy", "complexity": "medium", "question": "What causes the phases of the Moon?"},
    {"id": 6, "category": "astronomy", "complexity": "medium", "question": "Explain what a supernova is and why it's important"},
    {"id": 7, "category": "astronomy", "complexity": "high", "question": "What is dark matter and how do we know it exists?"},
    {"id": 8, "category": "astronomy", "complexity": "medium", "question": "How old is the universe and how was it formed?"},
    {"id": 9, "category": "astronomy", "complexity": "low", "question": "What are the names of Jupiter's four largest moons?"},
    {"id": 10, "category": "astronomy", "complexity": "medium", "question": "Explain the difference between a solar eclipse and a lunar eclipse"},
    {"id": 11, "category": "astronomy", "complexity": "medium", "question": "What is a pulsar and how was it discovered?"},
    {"id": 12, "category": "astronomy", "complexity": "medium", "question": "How does the Hubble Space Telescope work?"},
    {"id": 13, "category": "astronomy", "complexity": "medium", "question": "What is the Oort Cloud and where is it located?"},
    {"id": 14, "category": "astronomy", "complexity": "low", "question": "Explain the concept of light-year and how it's used"},
    {"id": 15, "category": "astronomy", "complexity": "medium", "question": "What are the main characteristics of a red giant star?"},
    {"id": 16, "category": "astronomy", "complexity": "high", "question": "How do astronomers measure the distance to nearby stars?"},
    {"id": 17, "category": "astronomy", "complexity": "low", "question": "What is the Great Red Spot on Jupiter?"},
    {"id": 18, "category": "astronomy", "complexity": "medium", "question": "Explain what a nebula is and give three examples"},
    {"id": 19, "category": "astronomy", "complexity": "low", "question": "What is the difference between a comet and an asteroid?"},
    {"id": 20, "category": "astronomy", "complexity": "medium", "question": "How does the James Webb Space Telescope differ from Hubble?"},
    {"id": 21, "category": "robotics", "complexity": "high", "question": "What is a PID controller and how does it work in robotics?"},
    {"id": 22, "category": "robotics", "complexity": "high", "question": "Explain the difference between forward and inverse kinematics"},
    {"id": 23, "category": "robotics", "complexity": "medium", "question": "How does a stepper motor differ from a servo motor?"},
    {"id": 24, "category": "robotics", "complexity": "high", "question": "What is SLAM in robotics and why is it important?"},
    {"id": 25, "category": "robotics", "complexity": "medium", "question": "Explain the concept of ROS (Robot Operating System)"},
    {"id": 26, "category": "physics", "complexity": "high", "question": "Explain Einstein's theory of general relativity in simple terms"},
    {"id": 27, "category": "physics", "complexity": "high", "question": "What is quantum entanglement and why is it important?"},
    {"id": 28, "category": "physics", "complexity": "medium", "question": "How does nuclear fusion differ from nuclear fission?"},
    {"id": 29, "category": "physics", "complexity": "high", "question": "Explain the concept of entropy and the second law of thermodynamics"},
    {"id": 30, "category": "physics", "complexity": "high", "question": "What are gravitational waves and how are they detected?"},
    {"id": 31, "category": "space_exploration", "complexity": "low", "question": "What was the Apollo 11 mission and why was it important?"},
    {"id": 32, "category": "space_exploration", "complexity": "medium", "question": "How does the SpaceX Starship work?"},
    {"id": 33, "category": "space_exploration", "complexity": "medium", "question": "What have we learned from the Mars rovers?"},
    {"id": 34, "category": "space_exploration", "complexity": "low", "question": "Explain the purpose of the International Space Station"},
    {"id": 35, "category": "space_exploration", "complexity": "low", "question": "When will humans return to the Moon with Artemis?"},
    {"id": 36, "category": "deep_questions", "complexity": "high", "question": "What is the meaning of life from a scientific perspective?"},
    {"id": 37, "category": "deep_questions", "complexity": "high", "question": "Does free will exist in a deterministic universe?"},
    {"id": 38, "category": "deep_questions", "complexity": "high", "question": "What is consciousness and can it be artificially created?"},
    {"id": 39, "category": "deep_questions", "complexity": "high", "question": "Is there a theory of everything in physics?"},
    {"id": 40, "category": "deep_questions", "complexity": "high", "question": "What happens to information inside a black hole?"},
    {"id": 41, "category": "quick_facts", "complexity": "low", "question": "Is the Sun a star?"},
    {"id": 42, "category": "quick_facts", "complexity": "low", "question": "Can humans live on Mars?"},
    {"id": 43, "category": "quick_facts", "complexity": "low", "question": "Does the Moon have gravity?"},
    {"id": 44, "category": "quick_facts", "complexity": "low", "question": "Is there water on the Moon?"},
    {"id": 45, "category": "quick_facts", "complexity": "low", "question": "Do black holes emit light?"},
    {"id": 46, "category": "astronomy", "complexity": "medium", "question": "What is the habitable zone around a star?"},
    {"id": 47, "category": "astronomy", "complexity": "high", "question": "Explain the concept of gravitational lensing"},
    {"id": 48, "category": "astronomy", "complexity": "medium", "question": "What are exoplanets and how are they detected?"},
    {"id": 49, "category": "astronomy", "complexity": "low", "question": "What is the difference between a galaxy and a nebula?"},
    {"id": 50, "category": "astronomy", "complexity": "high", "question": "Explain the Drake Equation and its purpose"},
    {"id": 51, "category": "robotics", "complexity": "medium", "question": "What are the main types of robot sensors?"},
    {"id": 52, "category": "robotics", "complexity": "medium", "question": "How does computer vision work in robotics?"},
    {"id": 53, "category": "robotics", "complexity": "low", "question": "What is the difference between teleoperation and autonomous control?"},
    {"id": 54, "category": "robotics", "complexity": "medium", "question": "Explain how obstacle avoidance algorithms work"},
    {"id": 55, "category": "robotics", "complexity": "medium", "question": "How do robotic arms achieve precision positioning?"},
    {"id": 56, "category": "physics", "complexity": "high", "question": "What is dark energy and how was it discovered?"},
    {"id": 57, "category": "physics", "complexity": "medium", "question": "How does a laser work?"},
    {"id": 58, "category": "physics", "complexity": "high", "question": "Explain the concept of time dilation"},
    {"id": 59, "category": "physics", "complexity": "high", "question": "What is the Standard Model of particle physics?"},
    {"id": 60, "category": "physics", "complexity": "high", "question": "How does superconductivity work?"},
    {"id": 61, "category": "space_exploration", "complexity": "medium", "question": "How does the Voyager spacecraft communicate from interstellar space?"},
    {"id": 62, "category": "space_exploration", "complexity": "medium", "question": "What is the Kepler mission and what did it discover?"},
    {"id": 63, "category": "space_exploration", "complexity": "medium", "question": "How do astronauts survive in space without gravity?"},
    {"id": 64, "category": "space_exploration", "complexity": "low", "question": "What is the future of commercial space tourism?"},
    {"id": 65, "category": "space_exploration", "complexity": "medium", "question": "How does the James Webb Space Telescope deploy its sunshield?"},
    {"id": 66, "category": "deep_questions", "complexity": "high", "question": "Are we living in a simulation?"},
    {"id": 67, "category": "deep_questions", "complexity": "high", "question": "What is the nature of time?"},
    {"id": 68, "category": "deep_questions", "complexity": "high", "question": "Why does the universe exist rather than nothing?"},
    {"id": 69, "category": "deep_questions", "complexity": "high", "question": "Can artificial intelligence achieve true understanding?"},
    {"id": 70, "category": "deep_questions", "complexity": "high", "question": "What is the ultimate fate of the universe?"},
    {"id": 71, "category": "quick_facts", "complexity": "low", "question": "Can we see the Great Wall of China from space?"},
    {"id": 72, "category": "quick_facts", "complexity": "low", "question": "Is Pluto larger than Earth's Moon?"},
    {"id": 73, "category": "quick_facts", "complexity": "low", "question": "Is there sound in space?"},
    {"id": 74, "category": "quick_facts", "complexity": "low", "question": "Can stars die?"},
    {"id": 75, "category": "quick_facts", "complexity": "low", "question": "Is our solar system moving through space?"},
    {"id": 76, "category": "astronomy", "complexity": "medium", "question": "What is the asteroid belt and where is it located?"},
    {"id": 77, "category": "astronomy", "complexity": "medium", "question": "Explain what a white dwarf is"},
    {"id": 78, "category": "astronomy", "complexity": "high", "question": "What is the Chandrasekhar limit?"},
    {"id": 79, "category": "astronomy", "complexity": "medium", "question": "What are the different types of galaxies?"},
    {"id": 80, "category": "astronomy", "complexity": "high", "question": "Explain the Fermi paradox"},
    {"id": 81, "category": "robotics", "complexity": "high", "question": "What is reinforcement learning in robotics?"},
    {"id": 82, "category": "robotics", "complexity": "medium", "question": "What are the challenges of underwater robotics?"},
    {"id": 83, "category": "robotics", "complexity": "medium", "question": "What is the Turing Test in AI and robotics?"},
    {"id": 84, "category": "robotics", "complexity": "medium", "question": "Explain the concept of swarm robotics"},
    {"id": 85, "category": "robotics", "complexity": "high", "question": "What are the safety considerations for industrial robots?"},
    {"id": 86, "category": "physics", "complexity": "medium", "question": "Explain the photoelectric effect"},
    {"id": 87, "category": "physics", "complexity": "high", "question": "Explain the double-slit experiment and its implications"},
    {"id": 88, "category": "physics", "complexity": "low", "question": "What is the difference between mass and weight?"},
    {"id": 89, "category": "physics", "complexity": "medium", "question": "How do electromagnetic waves propagate?"},
    {"id": 90, "category": "physics", "complexity": "high", "question": "Explain the Heisenberg uncertainty principle"},
    {"id": 91, "category": "space_exploration", "complexity": "medium", "question": "What is the Parker Solar Probe mission?"},
    {"id": 92, "category": "space_exploration", "complexity": "medium", "question": "How do space rockets achieve orbit?"},
    {"id": 93, "category": "space_exploration", "complexity": "low", "question": "What is the Europa Clipper mission?"},
    {"id": 94, "category": "space_exploration", "complexity": "high", "question": "Explain the concept of a space elevator"},
    {"id": 95, "category": "space_exploration", "complexity": "medium", "question": "What are the challenges of Mars colonization?"},
    {"id": 96, "category": "biology_chemistry", "complexity": "medium", "question": "How does photosynthesis work?"},
    {"id": 97, "category": "biology_chemistry", "complexity": "medium", "question": "What is DNA and how does it store information?"},
    {"id": 98, "category": "biology_chemistry", "complexity": "medium", "question": "How do vaccines work?"},
    {"id": 99, "category": "biology_chemistry", "complexity": "high", "question": "What is CRISPR gene editing?"},
    {"id": 100, "category": "biology_chemistry", "complexity": "medium", "question": "Explain evolution by natural selection"}
]


class BenchmarkWorker(QThread):
    progress_signal = pyqtSignal(int, int, str, str)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)
    
    def __init__(self, questions=None):
        super().__init__()
        self.running = True
        self.questions = questions or BENCHMARK_QUESTIONS
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.benchmark_dir = os.path.join(self.base_dir, "benchmark_results")
        os.makedirs(self.benchmark_dir, exist_ok=True)
        self.benchmark_file = os.path.join(self.benchmark_dir, "benchmark_results.json")
    
    def stop(self):
        self.running = False
    
    def test_question(self, model: str, question: Dict) -> Dict:
        start_time = time.time()
        
        # Adjust timeout based on model
        if "deepseek" in model:
            timeout = 300  # 5 minutes for deepseek
        elif "qwen" in model:
            timeout = 180  # 3 minutes for qwen
        else:
            timeout = 120  # 2 minutes for tinyllama
        
        payload = {
            "model": model,
            "prompt": question['question'],
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 2000  # Allow longer responses
            },
            "keep_alive": "30m"  # Keep model loaded for 30 minutes
        }
        
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                full_response = result.get("response", "")
                
                # Calculate depth score
                depth_score = self.calculate_depth_score(full_response)
                
                return {
                    "success": True,
                    "response_time": round(elapsed, 2),
                    "response_length": len(full_response),
                    "depth_score": depth_score,
                    "full_response": full_response,  # ← FULL RESPONSE SAVED!
                    "response_preview": full_response[:500] if len(full_response) > 500 else full_response,
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "response_time": round(elapsed, 2),
                    "response_length": 0,
                    "depth_score": 0,
                    "full_response": "",
                    "response_preview": "",
                    "error": f"HTTP {response.status_code}"
                }
        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "response_time": round(elapsed, 2),
                "response_length": 0,
                "depth_score": 0,
                "full_response": "",
                "response_preview": "",
                "error": f"Timeout after {timeout}s"
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "response_time": round(elapsed, 2),
                "response_length": 0,
                "depth_score": 0,
                "full_response": "",
                "response_preview": "",
                "error": str(e)
            }
    
    def calculate_depth_score(self, response: str) -> float:
        """Calculate response depth score (0-100)"""
        if not response:
            return 0
        
        words = len(response.split())
        sentences = response.count('.') + response.count('!') + response.count('?')
        paragraphs = response.count('\n\n') + 1
        
        score = 0
        score += min(30, words / 15)  # Up to 30 points for length (450+ words)
        score += min(20, sentences * 2)  # Up to 20 points for sentences
        score += min(15, paragraphs * 5)  # Up to 15 points for paragraphs
        score += 15 if 'example' in response.lower() else 0
        score += 10 if 'because' in response.lower() or 'therefore' in response.lower() else 0
        score += 5 if 'however' in response.lower() or 'whereas' in response.lower() else 0
        score += 5 if response.count('\n') >= 3 else 0  # Line breaks for structure
        
        return min(100, score)
    
    def run(self):
        results = {}
        all_results = []
        
        for model in MODELS_TO_TEST:
            if not self.running:
                break
            
            self.log_signal.emit(f"\n{'='*50}")
            self.log_signal.emit(f"🧪 Testing model: {model}")
            self.log_signal.emit(f"{'='*50}")
            
            model_results = []
            response_times = []
            depth_scores = []
            successes = 0
            
            for i, question in enumerate(self.questions):
                if not self.running:
                    break
                
                self.progress_signal.emit(i + 1, len(self.questions), model, question['question'][:50])
                
                result = self.test_question(model, question)
                result['question'] = question['question']
                result['category'] = question['category']
                result['complexity'] = question['complexity']
                result['question_id'] = question['id']
                
                model_results.append(result)
                
                if result['success']:
                    successes += 1
                    response_times.append(result['response_time'])
                    depth_scores.append(result['depth_score'])
                
                # Small delay between requests to avoid overwhelming
                time.sleep(0.3)
            
            # Calculate statistics
            avg_time = statistics.mean(response_times) if response_times else 0
            avg_depth = statistics.mean(depth_scores) if depth_scores else 0
            success_rate = (successes / len(self.questions)) * 100 if self.questions else 0
            
            results[model] = {
                "success_rate": round(success_rate, 1),
                "avg_response_time": round(avg_time, 2),
                "avg_depth_score": round(avg_depth, 1),
                "total_time": round(sum(response_times), 2),
                "successful": successes,
                "failed": len(self.questions) - successes
            }
            
            all_results.extend(model_results)
            
            self.log_signal.emit(f"\n✅ {model} Results:")
            self.log_signal.emit(f"   Success Rate: {results[model]['success_rate']}%")
            self.log_signal.emit(f"   Avg Response Time: {results[model]['avg_response_time']}s")
            self.log_signal.emit(f"   Avg Depth Score: {results[model]['avg_depth_score']}/100")
        
        # Determine winner
        winner = self.determine_winner(results)
        
        # Save benchmark results with FULL responses
        benchmark_data = {
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(self.questions),
            "models_tested": MODELS_TO_TEST,
            "winner": winner,
            "results": results,
            "detailed_results": all_results  # Contains full_response for each!
        }
        
        # Save to JSON file
        with open(self.benchmark_file, 'w', encoding='utf-8') as f:
            json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
        
        self.log_signal.emit(f"\n{'='*50}")
        self.log_signal.emit(f"🏆 WINNER: {winner['name']}")
        self.log_signal.emit(f"   Score: {winner['score']}/100")
        self.log_signal.emit(f"   Reason: {winner['reason']}")
        self.log_signal.emit(f"{'='*50}")
        self.log_signal.emit(f"\n📁 Benchmark results saved to: {self.benchmark_file}")
        self.log_signal.emit(f"📝 Full responses saved for all {len(all_results)} Q&A pairs!")
        
        self.finished_signal.emit(benchmark_data)
    
    def determine_winner(self, results: Dict) -> Dict:
        """Determine the best model based on weighted metrics"""
        scores = {}
        
        for model, data in results.items():
            # Weighted scoring (speed 35%, depth 45%, success 20%)
            # Speed matters but depth is more important for educational value
            speed_score = (1 / data['avg_response_time']) * 35 if data['avg_response_time'] > 0 else 0
            depth_score = data['avg_depth_score'] * 0.45
            success_score = data['success_rate'] * 0.2
            
            total_score = speed_score + depth_score + success_score
            
            scores[model] = {
                "score": round(total_score, 1),
                "speed_score": round(speed_score, 1),
                "depth_score": round(depth_score, 1),
                "success_score": round(success_score, 1)
            }
        
        # Find winner
        winner_model = max(scores, key=lambda x: scores[x]['score'])
        winner_score = scores[winner_model]['score']
        
        # Determine reason
        if scores[winner_model]['depth_score'] > scores[winner_model]['speed_score']:
            reason = "Superior response depth and quality"
        elif scores[winner_model]['speed_score'] > scores[winner_model]['depth_score']:
            reason = "Superior speed performance"
        else:
            reason = "Balanced performance across all metrics"
        
        return {
            "name": winner_model,
            "score": winner_score,
            "reason": reason,
            "details": scores[winner_model]
        }


class BenchmarkManager:
    """Singleton manager for benchmarks"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.benchmark_dir = os.path.join(self.base_dir, "benchmark_results")
        os.makedirs(self.benchmark_dir, exist_ok=True)
        self.benchmark_file = os.path.join(self.benchmark_dir, "benchmark_results.json")
    
    def get_last_benchmark(self) -> Dict:
        """Get the last benchmark results"""
        try:
            if os.path.exists(self.benchmark_file):
                with open(self.benchmark_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return None
    
    def clear_benchmark(self) -> bool:
        """Clear benchmark results"""
        try:
            if os.path.exists(self.benchmark_file):
                os.remove(self.benchmark_file)
            return True
        except:
            return False


benchmark_manager = BenchmarkManager()