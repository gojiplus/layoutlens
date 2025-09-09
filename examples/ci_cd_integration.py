"""CI/CD Integration examples for LayoutLens framework.

This module demonstrates how to integrate LayoutLens into
continuous integration and deployment pipelines.
"""

import os
import sys
import json
from pathlib import Path

from layoutlens import LayoutLens, Config
from layoutlens.test_runner import TestRunner


def github_actions_integration():
    """Example integration with GitHub Actions workflow."""
    
    # GitHub Actions sets these environment variables
    github_workspace = os.getenv('GITHUB_WORKSPACE', '.')
    github_sha = os.getenv('GITHUB_SHA', 'local')
    
    print(f"Running LayoutLens in GitHub Actions")
    print(f"Workspace: {github_workspace}")
    print(f"Commit SHA: {github_sha}")
    
    # Initialize with configuration
    config_path = Path(github_workspace) / ".github" / "layoutlens.yaml"
    tester = LayoutLens(config=str(config_path) if config_path.exists() else None)
    
    # Run test suite
    test_suite_path = Path(github_workspace) / "tests" / "ui_tests.yaml"
    if test_suite_path.exists():
        runner = TestRunner(tester.config)
        session = runner.run_test_suite(str(test_suite_path))
        
        # Set GitHub Actions output
        if os.getenv('GITHUB_ACTIONS'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"success_rate={session.success_rate}\n")
                f.write(f"total_tests={session.total_tests}\n")
                f.write(f"passed_tests={session.total_passed}\n")
        
        # Fail if success rate is too low
        if session.success_rate < 0.8:
            print(f"❌ UI tests failed: {session.success_rate:.2%} success rate")
            sys.exit(1)
        else:
            print(f"✅ UI tests passed: {session.success_rate:.2%} success rate")
    
    else:
        print("❌ No test suite found")
        sys.exit(1)


def jenkins_integration():
    """Example integration with Jenkins pipeline."""
    
    # Jenkins environment variables
    workspace = os.getenv('WORKSPACE', '.')
    build_number = os.getenv('BUILD_NUMBER', '0')
    job_name = os.getenv('JOB_NAME', 'layoutlens-job')
    
    print(f"Running LayoutLens in Jenkins")
    print(f"Job: {job_name}")
    print(f"Build: {build_number}")
    
    # Configure with Jenkins-specific settings
    config = Config()
    config.output.base_dir = f"{workspace}/layoutlens-reports"
    config.test.parallel_execution = True
    config.test.max_workers = 2
    
    tester = LayoutLens(config=config)
    runner = TestRunner(config)
    
    # Find test suites in workspace
    test_suites = list(Path(workspace).glob("**/*ui_tests*.yaml"))
    
    if test_suites:
        for suite_path in test_suites:
            print(f"Running test suite: {suite_path}")
            session = runner.run_test_suite(str(suite_path))
            
            # Generate JUnit-style XML for Jenkins
            generate_junit_xml(session, f"{workspace}/junit-{suite_path.stem}.xml")
        
        print("✅ All test suites completed")
    else:
        print("❌ No test suites found")
        sys.exit(1)


def docker_integration():
    """Example for running LayoutLens in Docker containers."""
    
    print("Running LayoutLens in Docker container")
    
    # Docker-specific configuration
    config = Config()
    config.screenshot.wait_timeout = 60000  # Longer timeout for containers
    config.output.base_dir = "/app/results"  # Container volume mount
    
    # Use environment variables for configuration
    if os.getenv('LAYOUTLENS_PARALLEL'):
        config.test.parallel_execution = True
        config.test.max_workers = int(os.getenv('LAYOUTLENS_WORKERS', '2'))
    
    tester = LayoutLens(config=config)
    
    # Look for test configuration in mounted volume
    test_config = "/app/config/test_suite.yaml"
    if Path(test_config).exists():
        runner = TestRunner(config)
        session = runner.run_test_suite(test_config)
        
        # Write results to mounted volume
        results_file = "/app/results/test_results.json"
        with open(results_file, 'w') as f:
            json.dump({
                "session_id": session.session_id,
                "success_rate": session.success_rate,
                "total_tests": session.total_tests,
                "passed_tests": session.total_passed,
                "duration": session.duration
            }, f, indent=2)
        
        print(f"Results written to: {results_file}")
        
        # Exit with appropriate code
        sys.exit(0 if session.success_rate > 0.8 else 1)
    
    else:
        print("❌ Test configuration not found")
        sys.exit(1)


def regression_testing_pipeline():
    """Example regression testing in deployment pipeline."""
    
    # Environment variables set by deployment system
    baseline_branch = os.getenv('BASELINE_BRANCH', 'main')
    current_branch = os.getenv('CURRENT_BRANCH', 'develop')
    baseline_dir = os.getenv('BASELINE_DIR', './baseline')
    current_dir = os.getenv('CURRENT_DIR', './current')
    
    print(f"Regression testing: {baseline_branch} → {current_branch}")
    
    # Set up regression testing
    config = Config()
    config.test.parallel_execution = True
    config.output.base_dir = f"./regression-{current_branch}"
    
    runner = TestRunner(config)
    
    # Run regression tests
    session = runner.run_regression_tests(
        baseline_dir=baseline_dir,
        current_dir=current_dir,
        test_patterns=["*.html", "pages/*.html", "components/*.html"],
        viewports=["desktop", "mobile_portrait", "tablet_portrait"]
    )
    
    # Analyze results
    regression_threshold = float(os.getenv('REGRESSION_THRESHOLD', '0.9'))
    
    if session.success_rate >= regression_threshold:
        print(f"✅ Regression tests passed: {session.success_rate:.2%}")
        
        # Generate deployment approval
        approval_file = "./deployment_approval.json"
        with open(approval_file, 'w') as f:
            json.dump({
                "approved": True,
                "reason": f"Regression tests passed with {session.success_rate:.2%} success rate",
                "timestamp": session.start_time,
                "test_results": {
                    "total_tests": session.total_tests,
                    "passed_tests": session.total_passed,
                    "success_rate": session.success_rate
                }
            }, f, indent=2)
        
        print(f"Deployment approved: {approval_file}")
        
    else:
        print(f"❌ Regression tests failed: {session.success_rate:.2%}")
        
        # Block deployment
        approval_file = "./deployment_approval.json"
        with open(approval_file, 'w') as f:
            json.dump({
                "approved": False,
                "reason": f"Regression tests failed with {session.success_rate:.2%} success rate (threshold: {regression_threshold:.2%})",
                "timestamp": session.start_time,
                "test_results": {
                    "total_tests": session.total_tests,
                    "passed_tests": session.total_passed,
                    "success_rate": session.success_rate
                }
            }, f, indent=2)
        
        print(f"Deployment blocked: {approval_file}")
        sys.exit(1)


def generate_junit_xml(session, output_path):
    """Generate JUnit XML format for CI systems."""
    
    from xml.etree.ElementTree import Element, SubElement, tostring
    import xml.dom.minidom
    
    # Create root testsuite element
    testsuite = Element("testsuite")
    testsuite.set("name", session.session_id)
    testsuite.set("tests", str(session.total_tests))
    testsuite.set("failures", str(session.total_tests - session.total_passed))
    testsuite.set("time", f"{session.duration:.2f}")
    
    # Add test cases
    for result in session.results:
        for test_result in result.test_results:
            testcase = SubElement(testsuite, "testcase")
            testcase.set("name", test_result.query)
            testcase.set("classname", f"{Path(result.html_path).stem}")
            testcase.set("time", f"{test_result.execution_time:.2f}")
            
            # Add failure if test didn't pass
            if "error" in test_result.answer.lower() or "no" in test_result.answer.lower():
                failure = SubElement(testcase, "failure")
                failure.set("message", "Visual test failed")
                failure.text = test_result.answer
    
    # Write XML file
    xml_str = xml.dom.minidom.parseString(tostring(testsuite)).toprettyxml(indent="  ")
    with open(output_path, 'w') as f:
        f.write(xml_str)
    
    print(f"JUnit XML generated: {output_path}")


if __name__ == "__main__":
    # Detect CI/CD environment and run appropriate integration
    
    if os.getenv('GITHUB_ACTIONS'):
        github_actions_integration()
    elif os.getenv('JENKINS_URL'):
        jenkins_integration()
    elif os.getenv('DOCKER_CONTAINER'):
        docker_integration()
    else:
        # Default to regression testing
        print("Running regression testing pipeline...")
        regression_testing_pipeline()