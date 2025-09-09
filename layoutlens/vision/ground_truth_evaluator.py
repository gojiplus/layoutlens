#!/usr/bin/env python3
"""
Ground Truth Test Evaluator

This script runs the LayoutLens framework against all ground truth test cases
and measures accuracy against known correct answers.

Usage:
    python ground_truth_evaluator.py
    python ground_truth_evaluator.py --test-case layout_alignment
    python ground_truth_evaluator.py --output-report results.json
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

from layoutlens import LayoutLens
import os
import openai

@dataclass
class TestResult:
    """Individual test result"""
    test_file: str
    question: str
    expected_answer: str
    ai_response: str
    is_correct: bool
    confidence: float
    processing_time: float
    error: str = None

@dataclass
class CategoryResults:
    """Results for a test category"""
    category: str
    total_tests: int
    correct: int
    incorrect: int
    accuracy: float
    avg_confidence: float
    avg_processing_time: float
    tests: List[TestResult]

class GroundTruthEvaluator:
    """Evaluates LayoutLens accuracy against ground truth test cases"""
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the evaluator
        
        Args:
            output_dir: Directory to save screenshots and results
        """
        self.project_root = Path(__file__).parent.parent.parent
        self.ground_truth_dir = self.project_root / "benchmarks" / "ground_truth_tests"
        self.output_dir = Path(output_dir) if output_dir else self.project_root / "layoutlens_output" / "ground_truth_results"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize LayoutLens
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable must be set")
            
        self.layout_lens = LayoutLens()
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(api_key=openai_key)
        
        self.test_categories = {
            "layout_alignment": "Layout Alignment Issues",
            "color_contrast": "Color Contrast Violations", 
            "responsive_design": "Responsive Design Problems",
            "accessibility": "Accessibility (WCAG) Violations"
        }
    
    def discover_test_files(self, category: str = None) -> Dict[str, List[Path]]:
        """
        Discover all ground truth test files
        
        Args:
            category: Specific category to test, or None for all
            
        Returns:
            Dictionary mapping categories to lists of test files
        """
        test_files = {}
        
        categories_to_scan = [category] if category else self.test_categories.keys()
        
        for cat in categories_to_scan:
            cat_dir = self.ground_truth_dir / cat
            if cat_dir.exists():
                html_files = list(cat_dir.glob("*.html"))
                if html_files:
                    test_files[cat] = html_files
                    print(f"Found {len(html_files)} test files in {cat}")
                else:
                    print(f"No HTML files found in {cat}")
            else:
                print(f"Category directory not found: {cat}")
        
        return test_files
    
    def extract_test_metadata(self, html_file: Path) -> List[Dict[str, Any]]:
        """
        Extract ground truth metadata from HTML file
        
        Args:
            html_file: Path to HTML test file
            
        Returns:
            List of test questions and expected answers
        """
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse embedded test metadata
            # Look for data-question and data-correct-answer attributes
            import re
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(content, 'html.parser')
            test_metadata = []
            
            # Find all elements with data-question attributes
            question_elements = soup.find_all(attrs={"data-question": True})
            
            for q_elem in question_elements:
                question = q_elem.get("data-question")
                
                # Find corresponding answer element (sibling with data-correct-answer)
                answer_elem = q_elem.find(attrs={"data-correct-answer": True})
                if not answer_elem:
                    # Try finding in next sibling
                    answer_elem = q_elem.find_next(attrs={"data-correct-answer": True})
                
                if answer_elem:
                    expected_answer = answer_elem.get("data-correct-answer")
                    
                    # Extract additional metadata
                    metadata = {
                        "question": question,
                        "expected_answer": expected_answer,
                        "issue_type": q_elem.get("data-issue-type", "unknown"),
                        "severity": q_elem.get("data-severity", "unknown"),
                        "measurable": q_elem.get("data-measurable", "false") == "true"
                    }
                    
                    # Look for specific measurements
                    measured_elem = q_elem.find(attrs={"data-measured-ratio": True}) or \
                                  q_elem.find(attrs={"data-measured-size": True}) or \
                                  q_elem.find(attrs={"data-specific-issue": True})
                    
                    if measured_elem:
                        for attr in ["data-measured-ratio", "data-measured-size", "data-specific-issue"]:
                            if measured_elem.get(attr):
                                metadata["measured_value"] = measured_elem.get(attr)
                                break
                    
                    test_metadata.append(metadata)
            
            return test_metadata
            
        except Exception as e:
            print(f"Error extracting metadata from {html_file}: {e}")
            return []
    
    def run_layoutlens_test(self, html_file: Path, question: str) -> Tuple[str, float, float]:
        """
        Run LayoutLens analysis on a test file
        
        Args:
            html_file: Path to HTML test file
            question: Question to ask about the page
            
        Returns:
            Tuple of (response, confidence, processing_time)
        """
        start_time = time.time()
        
        try:
            # Use LayoutLens test_page method with custom query
            result = self.layout_lens.test_page(
                html_path=str(html_file),
                queries=[question],
                auto_generate_queries=False
            )
            
            if not result or not result.test_results:
                raise Exception("No test results from LayoutLens")
            
            # Get the first test result (our question)
            test_result = result.test_results[0]
            response = test_result.answer
            
            processing_time = time.time() - start_time
            confidence = self._estimate_confidence(response)
            
            return response, confidence, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            raise Exception(f"LayoutLens test failed: {e}")
    
    def _analyze_with_openai_vision(self, screenshot_path: str, question: str) -> str:
        """
        Analyze screenshot with OpenAI Vision API
        
        Args:
            screenshot_path: Path to screenshot file
            question: Question about the image
            
        Returns:
            AI response
        """
        import base64
        
        # Read and encode image
        with open(screenshot_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode()
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",  # Use vision model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Please analyze this screenshot and answer the question: {question}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    def _estimate_confidence(self, response: str) -> float:
        """
        Estimate confidence based on response content (simple heuristic)
        
        Args:
            response: AI response text
            
        Returns:
            Confidence score between 0 and 1
        """
        # Simple heuristic - count confident language
        confident_words = ["clearly", "obvious", "definitely", "certainly", "precisely", "exactly"]
        uncertain_words = ["might", "could", "possibly", "perhaps", "seems", "appears"]
        
        response_lower = response.lower()
        confident_count = sum(1 for word in confident_words if word in response_lower)
        uncertain_count = sum(1 for word in uncertain_words if word in response_lower)
        
        # Base confidence
        base_confidence = 0.7
        
        # Adjust based on language
        confidence_adjustment = (confident_count - uncertain_count) * 0.1
        confidence = max(0.1, min(1.0, base_confidence + confidence_adjustment))
        
        return confidence
    
    def evaluate_response(self, expected: str, actual: str) -> bool:
        """
        Evaluate if the AI response matches the expected answer
        
        Args:
            expected: Expected answer
            actual: AI response
            
        Returns:
            True if correct, False otherwise
        """
        expected_lower = expected.lower().strip()
        actual_lower = actual.lower().strip()
        
        # Handle yes/no questions
        if expected_lower in ["yes", "no"]:
            # Look for clear yes/no indicators in response
            if expected_lower == "yes":
                return any(phrase in actual_lower for phrase in ["yes", "correct", "properly", "meets", "passes"])
            else:
                return any(phrase in actual_lower for phrase in ["no", "incorrect", "fails", "doesn't", "violation", "problem"])
        
        # Handle partial answers
        if expected_lower == "partial":
            return any(phrase in actual_lower for phrase in ["partial", "some", "mixed", "partially"])
        
        # Handle numeric answers (contrast ratios, etc.)
        if ":" in expected_lower:  # Likely a ratio
            return expected_lower in actual_lower
        
        # General keyword matching
        expected_keywords = expected_lower.split()
        matches = sum(1 for keyword in expected_keywords if keyword in actual_lower)
        
        # Consider correct if most keywords match
        return matches / len(expected_keywords) >= 0.6
    
    def run_category_tests(self, category: str, test_files: List[Path]) -> CategoryResults:
        """
        Run all tests in a category
        
        Args:
            category: Category name
            test_files: List of HTML test files
            
        Returns:
            CategoryResults object
        """
        print(f"\n=== Testing {self.test_categories[category]} ===")
        
        all_tests = []
        correct_count = 0
        total_confidence = 0
        total_time = 0
        
        for html_file in test_files:
            print(f"\nTesting: {html_file.name}")
            
            # Extract test metadata
            test_metadata = self.extract_test_metadata(html_file)
            
            if not test_metadata:
                print(f"  No test metadata found in {html_file.name}")
                continue
            
            for test_data in test_metadata:
                question = test_data["question"]
                expected_answer = test_data["expected_answer"]
                
                print(f"  Question: {question}")
                print(f"  Expected: {expected_answer}")
                
                try:
                    # Run the test
                    ai_response, confidence, processing_time = self.run_layoutlens_test(html_file, question)
                    
                    print(f"  AI Response: {ai_response}")
                    print(f"  Processing Time: {processing_time:.2f}s")
                    
                    # Evaluate correctness
                    is_correct = self.evaluate_response(expected_answer, ai_response)
                    
                    print(f"  Result: {'✓ CORRECT' if is_correct else '✗ INCORRECT'}")
                    
                    # Record result
                    test_result = TestResult(
                        test_file=html_file.name,
                        question=question,
                        expected_answer=expected_answer,
                        ai_response=ai_response,
                        is_correct=is_correct,
                        confidence=confidence,
                        processing_time=processing_time
                    )
                    
                    all_tests.append(test_result)
                    
                    if is_correct:
                        correct_count += 1
                    
                    total_confidence += confidence
                    total_time += processing_time
                    
                except Exception as e:
                    print(f"  Error: {e}")
                    
                    test_result = TestResult(
                        test_file=html_file.name,
                        question=question,
                        expected_answer=expected_answer,
                        ai_response="ERROR",
                        is_correct=False,
                        confidence=0.0,
                        processing_time=0.0,
                        error=str(e)
                    )
                    
                    all_tests.append(test_result)
        
        # Calculate category statistics
        total_tests = len(all_tests)
        accuracy = correct_count / total_tests if total_tests > 0 else 0
        avg_confidence = total_confidence / total_tests if total_tests > 0 else 0
        avg_processing_time = total_time / total_tests if total_tests > 0 else 0
        
        return CategoryResults(
            category=category,
            total_tests=total_tests,
            correct=correct_count,
            incorrect=total_tests - correct_count,
            accuracy=accuracy,
            avg_confidence=avg_confidence,
            avg_processing_time=avg_processing_time,
            tests=all_tests
        )
    
    def run_evaluation(self, category: str = None) -> Dict[str, CategoryResults]:
        """
        Run complete evaluation
        
        Args:
            category: Specific category to test, or None for all
            
        Returns:
            Dictionary mapping categories to results
        """
        print("Starting Ground Truth Evaluation")
        print("=" * 50)
        
        # Discover test files
        test_files = self.discover_test_files(category)
        
        if not test_files:
            print("No test files found!")
            return {}
        
        # Run tests for each category
        results = {}
        
        for cat, files in test_files.items():
            try:
                category_results = self.run_category_tests(cat, files)
                results[cat] = category_results
            except Exception as e:
                print(f"Error testing category {cat}: {e}")
        
        return results
    
    def generate_report(self, results: Dict[str, CategoryResults], output_file: str = None):
        """
        Generate evaluation report
        
        Args:
            results: Dictionary of category results
            output_file: Optional path to save JSON report
        """
        print("\n" + "=" * 60)
        print("GROUND TRUTH EVALUATION REPORT")
        print("=" * 60)
        
        overall_correct = 0
        overall_total = 0
        overall_time = 0
        
        for category, result in results.items():
            print(f"\n{self.test_categories.get(category, category).upper()}")
            print("-" * 40)
            print(f"Tests: {result.total_tests}")
            print(f"Correct: {result.correct}")
            print(f"Incorrect: {result.incorrect}")
            print(f"Accuracy: {result.accuracy:.1%}")
            print(f"Avg Confidence: {result.avg_confidence:.2f}")
            print(f"Avg Processing Time: {result.avg_processing_time:.2f}s")
            
            # Show detailed results for incorrect answers
            incorrect_tests = [t for t in result.tests if not t.is_correct]
            if incorrect_tests:
                print(f"\nIncorrect Answers ({len(incorrect_tests)}):")
                for test in incorrect_tests:
                    print(f"  • {test.test_file}: {test.question}")
                    print(f"    Expected: {test.expected_answer}")
                    print(f"    Got: {test.ai_response}")
            
            overall_correct += result.correct
            overall_total += result.total_tests
            overall_time += result.avg_processing_time * result.total_tests
        
        # Overall statistics
        if overall_total > 0:
            overall_accuracy = overall_correct / overall_total
            avg_overall_time = overall_time / overall_total
            
            print(f"\nOVERALL RESULTS")
            print("-" * 40)
            print(f"Total Tests: {overall_total}")
            print(f"Overall Accuracy: {overall_accuracy:.1%}")
            print(f"Avg Processing Time: {avg_overall_time:.2f}s")
            
            # Performance assessment
            if overall_accuracy >= 0.9:
                performance = "Excellent"
            elif overall_accuracy >= 0.8:
                performance = "Good"
            elif overall_accuracy >= 0.7:
                performance = "Fair"
            else:
                performance = "Needs Improvement"
            
            print(f"Performance Rating: {performance}")
        
        # Save JSON report if requested
        if output_file:
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "overall_accuracy": overall_accuracy if overall_total > 0 else 0,
                "overall_tests": overall_total,
                "categories": {}
            }
            
            for category, result in results.items():
                report_data["categories"][category] = {
                    "accuracy": result.accuracy,
                    "total_tests": result.total_tests,
                    "correct": result.correct,
                    "avg_confidence": result.avg_confidence,
                    "avg_processing_time": result.avg_processing_time,
                    "tests": [
                        {
                            "test_file": t.test_file,
                            "question": t.question,
                            "expected": t.expected_answer,
                            "actual": t.ai_response,
                            "correct": t.is_correct,
                            "confidence": t.confidence,
                            "processing_time": t.processing_time,
                            "error": t.error
                        }
                        for t in result.tests
                    ]
                }
            
            with open(output_file, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            print(f"\nDetailed report saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Evaluate LayoutLens against ground truth test cases")
    parser.add_argument("--test-case", choices=["layout_alignment", "color_contrast", "responsive_design", "accessibility"], 
                       help="Specific test category to run")
    parser.add_argument("--output-report", help="Path to save JSON report")
    parser.add_argument("--output-dir", help="Directory for screenshots and results")
    
    args = parser.parse_args()
    
    # Initialize evaluator
    evaluator = GroundTruthEvaluator(output_dir=args.output_dir)
    
    # Run evaluation
    results = evaluator.run_evaluation(category=args.test_case)
    
    # Generate report
    evaluator.generate_report(results, output_file=args.output_report)

if __name__ == "__main__":
    main()