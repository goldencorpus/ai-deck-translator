from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="ai_deck_translator",
    version="2.0.0",
    author="AI Deck Translator Team",
    author_email="your.email@example.com",
    description="Translate presentations (Google Slides and PowerPoint) between different languages",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ai-deck-translator",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "ai-deck-translator=ai_deck_translator.run:main",
        ],
    },
    include_package_data=True,
) 