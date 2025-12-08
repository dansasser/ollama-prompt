from setuptools import setup, find_packages

setup(
    name='ollama-prompt',
    version='1.2.0',
    packages=find_packages(),
    py_modules=['ollama_prompt'],
    install_requires=['ollama', 'llm-fs-tools>=0.1.0'],
    entry_points={
        'console_scripts': [
            'ollama-prompt=ollama_prompt.cli:main'
        ]
    },
    author="Daniel T Sasser II",
    description="Ollama CLI prompt tool for local LLM code analysis",
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/dansasser/ollama-prompt",
    python_requires=">=3.10"
)
