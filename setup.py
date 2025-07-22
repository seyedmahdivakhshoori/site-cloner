from setuptools import setup, find_packages

setup(
    name='site-cloner',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'PyQt5>=5.15',
        'beautifulsoup4>=4.11',
        'aiohttp>=3.8',
        'playwright>=1.44',
    ],
    entry_points={
        'console_scripts': [
            'site-cloner=site_cloner.core:run_gui',
        ],
    },
)
