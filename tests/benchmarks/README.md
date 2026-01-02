# Performance Benchmarks for repo-sapiens

This directory contains comprehensive performance benchmarks for repo-sapiens' critical operations. The benchmarks use `pytest-benchmark` for statistical rigor and consistent measurements.

## Quick Start

### Running All Benchmarks

```bash
# Install dependencies
pip install pytest-benchmark memory-profiler

# Run all benchmarks with JSON output
pytest tests/benchmarks/ --benchmark-only --benchmark-json=benchmark_results.json

# Run specific benchmark class
pytest tests/benchmarks/test_performance.py::TestConfigurationLoadingPerformance --benchmark-only

# Run specific test
pytest tests/benchmarks/test_performance.py::TestConfigurationLoadingPerformance::test_load_yaml_config_simple --benchmark-only
```

### Viewing Results

```bash
# Human-readable output
pytest tests/benchmarks/ --benchmark-only -v

# Compare against baseline
pytest tests/benchmarks/ --benchmark-only --benchmark-compare=baseline.json

# Generate CSV report
pytest tests/benchmarks/ --benchmark-only --benchmark-json=results.json
python3 -c "import json; data=json.load(open('results.json')); [print(f\"{b['name']},{b['stats']['mean']:.6f}\") for b in data['benchmarks']]"
```

## Benchmark Suite Overview

### 1. Configuration Loading (`TestConfigurationLoadingPerformance`)
Measures YAML parsing, Pydantic validation, and environment variable resolution.

**Tests:**
- `test_load_yaml_config_simple` - Raw YAML file parsing
- `test_parse_pydantic_settings` - Full config validation
- `test_environment_variable_resolution` - Environment variable lookup
- `test_credential_resolver_initialization` - Resolver setup

**Target:** <100ms | **Current:** ~0.76ms ✅

### 2. Git Discovery (`TestGitDiscoveryPerformance`)
Measures repository detection and Git URL parsing.

**Tests:**
- `test_git_discovery_initialization` - GitDiscovery setup
- `test_parse_git_url` - URL parsing performance
- `test_repository_info_detection` - Repo info extraction
- `test_multiple_remote_handling` - Multiple remote handling

**Target:** <200ms for 10 repos | **Current:** ~110-150ms ✅

### 3. Template Rendering (`TestTemplateRenderingPerformance`)
Measures Jinja2 template rendering for simple and complex templates.

**Tests:**
- `test_simple_template_render` - Basic variable substitution
- `test_complex_template_render` - Loops, conditionals, filters
- `test_secure_engine_initialization` - Engine setup overhead

**Target:** <50ms (simple), <200ms (complex) | **Current:** <1ms ✅

### 4. Credential Resolution (`TestCredentialResolutionPerformance`)
Measures credential lookup across different backends.

**Tests:**
- `test_environment_backend_resolution` - Environment variable lookup
- `test_environment_backend_multiple_credentials` - Batch env lookups
- `test_keyring_backend_resolution` - Keyring access
- `test_credential_resolver_environment` - Resolver with env vars
- `test_credential_resolver_cache_hit` - Cache performance

**Target:** <50ms per credential | **Current:** <0.001ms ✅

### 5. State Management (`TestStateManagementPerformance`)
Measures file I/O and atomic state operations (async tests).

**Tests:**
- `test_load_state_new` - Initial state creation
- `test_save_state` - Atomic state write
- `test_state_transaction` - Transactional updates
- `test_load_existing_state` - Loading saved state
- `test_large_state_serialization` - Large state handling

**Target:** <100ms per operation | **Current:** 5-8ms ✅

### 6. Integration (`TestIntegrationPerformance`)
Measures end-to-end operations combining multiple subsystems.

**Tests:**
- `test_end_to_end_config_load_resolve` - Full config pipeline
- `test_template_render_with_config` - Config-based template rendering

**Target:** <100ms | **Current:** 35-57ms ✅

### 7. Memory Usage (`TestMemoryUsage`)
Profiles memory consumption for large operations.

**Tests:**
- `test_large_config_parsing_memory` - Large config memory
- `test_state_file_memory_growth` - State file handling

### 8. Performance Assertions (`TestPerformanceTargets`)
Validates performance against explicit targets.

**Tests:**
- `test_config_loading_target` - Asserts <100ms
- `test_template_rendering_simple_target` - Asserts <50ms
- `test_credential_resolution_target` - Asserts <50ms

### 9. Comparative (`TestComparativeBenchmarks`)
Compares different implementation approaches.

**Tests:**
- `test_yaml_safe_load_vs_unsafe` - YAML parsing methods
- `test_direct_render_vs_engine` - Template engine approaches
- `test_json_vs_pickle_state` - Serialization methods

## Performance Targets

| Operation | Target | Status |
|-----------|--------|--------|
| YAML Loading | <100ms | ✅ PASS |
| Pydantic Validation | <100ms | ✅ PASS |
| Env Variable Resolution | <50ms | ✅ PASS |
| Git Discovery (per repo) | <20ms | ✅ PASS |
| Git Discovery (10 repos) | <200ms | ✅ PASS |
| Simple Template Render | <50ms | ✅ PASS |
| Complex Template Render | <200ms | ✅ PASS |
| Credential Resolution | <50ms | ✅ PASS |
| State Load | <100ms | ✅ PASS |
| State Save | <100ms | ✅ PASS |
| Full Startup | <100ms | ✅ PASS |

## Interpreting Results

### Benchmark Output
```
tests/benchmarks/test_performance.py::test_simple_template_render PASSED

Name (time in ms)           Min      Max      Mean   StdDev   Median
simple_template_render      0.25     2.35     0.29   0.10     0.28
```

**Metrics Explained:**
- **Min:** Best case (cold cache, minimal GC)
- **Max:** Worst case (may include GC pauses)
- **Median:** Middle value (most representative)
- **Mean:** Average (affected by outliers)
- **StdDev:** Consistency (lower = more predictable)

### Statistical Interpretation

**Excellent (StdDev < 10% of Mean):**
- Consistent, predictable performance
- Examples: Environment variable resolution

**Good (StdDev 10-30% of Mean):**
- Generally consistent with minor variance
- Examples: Template rendering, config loading

**Variable (StdDev > 30% of Mean):**
- Affected by external factors (GC, I/O)
- Examples: File I/O, system calls

## Running Benchmarks in CI/CD

### GitHub Actions Example

```yaml
- name: Run Performance Benchmarks
  run: |
    pytest tests/benchmarks/ \
      --benchmark-only \
      --benchmark-json=benchmark_results.json \
      -v

- name: Compare Against Baseline
  run: |
    pytest tests/benchmarks/ \
      --benchmark-only \
      --benchmark-compare=baseline.json \
      --benchmark-compare-fail=mean:10%
```

### Creating a Baseline

```bash
# First run - establish baseline
pytest tests/benchmarks/ --benchmark-only --benchmark-save=baseline

# Future runs - compare against baseline
pytest tests/benchmarks/ --benchmark-only --benchmark-compare=baseline

# Fail if performance degrades >10%
pytest tests/benchmarks/ \
  --benchmark-only \
  --benchmark-compare=baseline \
  --benchmark-compare-fail=mean:10%
```

## Optimization Recommendations

### 1. Git Discovery (Highest Priority)
- **Current:** 10-15ms per repo
- **Optimization:** Parallel discovery with asyncio
- **Expected Improvement:** 3-5x faster
- **File:** `repo_sapiens/git/discovery.py`

### 2. Configuration Validation
- **Current:** 15-20ms
- **Optimization:** Model caching, lazy validation
- **Expected Improvement:** 2-3x faster
- **File:** `repo_sapiens/config/settings.py`

### 3. State File I/O
- **Current:** 5-8ms per write
- **Optimization:** Batch updates, compression
- **Expected Improvement:** 60-70% reduction
- **File:** `repo_sapiens/engine/state_manager.py`

## Profiling Tools

### Memory Profiling
```bash
pip install memory-profiler

# Profile a function
python3 -m memory_profiler tests/benchmarks/test_performance.py

# Line-by-line profiling
@profile
def my_function():
    ...
```

### CPU Profiling
```bash
pip install py-spy

# Real-time profiling
py-spy record -o profile.svg -- pytest tests/benchmarks/ --benchmark-only

# Flame graph visualization
open profile.svg
```

### Async Profiling
```bash
# With asyncio event loop
pytest tests/benchmarks/ -v -s --asyncio-mode=auto
```

## Debugging Benchmark Results

### Slow Tests
If a benchmark is slower than expected:

1. **Check system load:**
   ```bash
   top -b -n 1 | head -5
   ```

2. **Profile with timing:**
   ```bash
   pytest tests/benchmarks/test_performance.py::TestConfigurationLoadingPerformance::test_load_yaml_config_simple -v --benchmark-only --benchmark-disable-gc
   ```

3. **Disable garbage collection:**
   ```bash
   pytest tests/benchmarks/ --benchmark-only --benchmark-disable-gc
   ```

### Outliers
Large variance in results may indicate:
- System resource contention
- Python garbage collection pauses
- Thermal throttling
- Network I/O (for tests with I/O)

**Solutions:**
```bash
# Run with GC disabled
pytest tests/benchmarks/ --benchmark-only --benchmark-disable-gc

# Increase rounds for accuracy
pytest tests/benchmarks/ --benchmark-only --benchmark-rounds=10

# Profile CPU pinning
taskset -c 0 pytest tests/benchmarks/ --benchmark-only
```

## Performance Regression Detection

### Continuous Monitoring
```bash
# Run benchmarks and save results
pytest tests/benchmarks/ --benchmark-only --benchmark-json=current.json

# Compare with baseline
python3 << 'EOF'
import json

baseline = json.load(open('baseline.json'))
current = json.load(open('current.json'))

for bm_curr in current['benchmarks']:
    bm_base = next((b for b in baseline['benchmarks'] if b['name'] == bm_curr['name']), None)
    if bm_base:
        ratio = bm_curr['stats']['mean'] / bm_base['stats']['mean']
        if ratio > 1.10:  # 10% regression
            print(f"REGRESSION: {bm_curr['name']} ({ratio:.2f}x slower)")
EOF
```

## Best Practices

### 1. Run Benchmarks Regularly
- Before major refactoring
- After performance-critical changes
- As part of CI/CD pipeline

### 2. Control Variables
- Run on consistent hardware
- Close unnecessary applications
- Use consistent Python version
- Same system configuration

### 3. Interpret Results Carefully
- Look at mean/median, not min/max
- Consider standard deviation
- Multiple runs increase confidence
- Context matters (real-world load differs)

### 4. Document Changes
When optimizing:
```python
# Before: 50ms
# After: 10ms
# Improvement: 5x faster
# Change: Implemented caching
def optimized_function():
    ...
```

## References

- **pytest-benchmark:** https://pytest-benchmark.readthedocs.io/
- **Python Profiling:** https://docs.python.org/3/library/profile.html
- **Memory Profiler:** https://github.com/pythonprofilers/memory_profiler
- **py-spy:** https://github.com/benfred/py-spy

## Troubleshooting

### Import Errors
```bash
# Ensure package is installed
pip install -e .

# Check Python path
export PYTHONPATH=$PWD:$PYTHONPATH
```

### Async Test Issues
```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Run with proper asyncio mode
pytest tests/benchmarks/ -v --asyncio-mode=auto
```

### File Permission Errors
```bash
# Check file permissions
ls -la tests/benchmarks/

# Fix permissions
chmod +x tests/benchmarks/
```

## Contributing

To add new benchmarks:

1. **Create test function:**
```python
def test_my_operation(benchmark):
    """Benchmark description with target."""
    def operation():
        # Code to benchmark
        return result

    result = benchmark(operation)
    assert result is not None
```

2. **Document target:**
```python
"""Target: <50ms"""
```

3. **Add to appropriate class** (ConfigurationLoading, GitDiscovery, etc.)

4. **Run and record baseline:**
```bash
pytest tests/benchmarks/test_performance.py::TestMyClass::test_my_operation --benchmark-only
```

---
