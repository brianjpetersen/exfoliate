import os
import sys
import setuptools


__where__ = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(__where__, 'VERSION'), 'rb') as f:
    __version__ = f.read().decode('ascii').strip()


# would prefer to just use markdown, but not compatible with setuptools; see the following Github
# issue for more information: https://github.com/pypa/packaging-problems/issues/46
with open(os.path.join(__where__, 'DESCRIPTION.rst'), 'rb') as f:
    long_description = f.read().decode('utf-8').strip()


class TestCommand(setuptools.Command):
    
    description = 'Test the exfoliate package with pytest.'
    user_options = []
    
    def initialize_options(self): pass

    def finalize_options(self): pass
    
    def run(self):
        import pytest
        exit_code = pytest.main(['tests.py', ])
        sys.exit(exit_code)


class PublishCommand(setuptools.Command):
    
    description = 'Build and publish the package.'
    user_options = []
    
    def initialize_options(self): pass

    def finalize_options(self): pass

    def run(self):
        try:
            print('removing previous builds...')
            shutil.rmtree(os.path.join(here, 'dist'))
        except FileNotFoundError:
            pass
        print('building Source and Wheel (universal) distribution...')
        os.system(f'{sys.executable} setup.py sdist bdist_wheel --universal')
        print('uploading the package to PyPi via Twine...')
        os.system('twine upload dist/*')
        sys.exit()


class BenchmarkCommand(setuptools.Command):
    
    description = 'Benchmark exfoliate against pure aiohttp.'
    user_options = []
    
    def initialize_options(self): pass

    def finalize_options(self): pass

    def run(self):
        os.system(f'{sys.executable} benchmark.py')
        sys.exit()
    

setuptools.setup(
    name='exfoliate',
    version=__version__,
    description='The asynchronous Python HTTP client for developers who prefer synchronous Python.',
    long_description=long_description,
    author='Brian J Petersen',
    author_email='brianjpetersen@gmail.com',
    url='https://github.com/brianjpetersen/exfoliate',
    py_modules=['exfoliate', ],
    install_requires=['aiohttp>=2.2.5', ],
    tests_require=['pytest', 'requests', ],
    include_package_data=True,
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    cmdclass={
        'publish': PublishCommand,
        'test': TestCommand,
        'benchmark': BenchmarkCommand,
    },
)
