from setuptools import setup, find_packages
import sys, os

version = '0.4'

setup(name='friendly_curl',
      version=version,
      description="A friendly interface to PyCURL.",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Nick Pilon, Gavin Carothers',
      author_email='npilon@oreilly.com, gavin@oreilly.com',
      url='',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
	"pycurl>=7.16.4",
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
