from setuptools import setup, find_packages

setup(
    name='nonebot_plugin_poker',
    version='0.1.1',
    packages=find_packages(),
    install_requires=[
        "nonebot2>=2.0.0",
    ],
    author='MoonofBridge24',
    author_email='moonofbridge24@foxmail.com',
    description='详见readme',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/MoonofBridge24/nonebot_plugin_poker',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)