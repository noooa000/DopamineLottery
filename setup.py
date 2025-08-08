from setuptools import setup

APP = ['Connect4.py']
OPTIONS = {
    'iconfile': 'icon2.icn',
    'packages': ['tkinter', 'random', 'winsound']
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
