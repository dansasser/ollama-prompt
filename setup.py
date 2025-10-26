from setuptools import setup, find_packages

setup(
    name='ollama-prompt',
    version='1.0.0',
    packages=find_packages(),
    py_modules=['ollama_prompt'],
    install_requires=['ollama'],
    entry_points={
        'console_scripts': [
            'ollama-prompt=ollama_prompt:main'
        ]
    },
    author="Daniel T Sasser II",
    description="Ollama CLI prompt tool for local LLM code analysis",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ollama-prompt",  # set to your repo if desired
    python_requires=">=3.7"
)
