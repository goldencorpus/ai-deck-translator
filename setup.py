from setuptools import setup, find_packages

setup(
    name="ai-deck-translator",
    version="2.0.0",
    author="Emmanuel Prouveze",
    author_email="example@example.com",
    description="AI-powered deck/presentation translator with support for multiple formats",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/eprouveze/ai-deck-translator",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "google-auth>=2.19.0",
        "google-auth-oauthlib>=1.0.0",
        "google-auth-httplib2>=0.1.0",
        "google-api-python-client>=2.88.0",
        "anthropic>=0.5.0",
        "tqdm>=4.65.0",
        "flask>=2.3.2",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ai-deck-translator=ai_deck_translator.run:main",
        ],
    },
) 