from setuptools import setup

setup(
    name='thehivebackup',
    version='0.1.1',
    url='https://github.com/IFX-CDC/thehivebackup',
    author='Anton Piiroja & Jonas Plum',
    description='Backup and restore TheHive remotely',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=['thehivebackup'],
    install_requires=[
        'requests==2.25.1',
    ],
    entry_points={
        'console_scripts':
            ['thehivebackup = thehivebackup.main:main']
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    zip_safe=False,
)
