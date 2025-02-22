import contextlib
import glob
import logging
import json
import os
import shutil
import subprocess
import sys
import tempfile

import begin

from . import generate


@contextlib.contextmanager
def tempdir(debug=False):
    _dir = tempfile.mkdtemp()
    try:
        yield _dir
    finally:
        if debug:
            logging.info('Leaving tmpdir {} alone'.format(_dir))
        else:
            shutil.rmtree(_dir)


def use_pip_cache():
    """Use env variable TRAVIS_RUNNER_PIP_CACHE as persistent pip cache
    """
    pip_cache_dir = os.environ.get('TRAVIS_RUNNER_PIP_CACHE')
    if pip_cache_dir is not None:
        return '-v {}:/root/.cache/pip'.format(pip_cache_dir)
    else:
        return ''


@begin.start
@begin.logging
def main(debug=False, dry_run=False, image=None, user=None):
    image = image or os.environ.get('TRAVIS_RUNNER_IMAGE', 'ubuntu:precise')
    user = user or os.environ.get('TRAVIS_RUNNER_USER')
    failed = True

    with tempdir(debug) as _dir:
        generate.main(destdir=_dir, user=user)
        if dry_run:
            return

        for env in glob.glob(os.path.join(_dir, '.travis-runner-*.sh')):
            links = json.load(open(env + '.links'))
            link_arg = ''
            for link in links:
                subprocess.check_call(
                    'docker run --name {name} {args} -d {image}'
                    .format(**link),
                    shell=True)
                link_arg += '--link {name}:{link}'.format(**link)

            cmd = ' '.join((
                'docker run {0} --rm -e http_proxy=$http_proxy',
                '-v $(pwd):/src',
                '-v {1}:/{1}',
                use_pip_cache(),
                '{2} bash -x {3}')).format(link_arg, _dir, image, env)
            try:
                subprocess.check_call(cmd, shell=True)
                failed = False
            except subprocess.CalledProcessError:
                if links:
                    for link in links:
                        subprocess.check_call(
                            'docker rm -f {name}'.format(**link), shell=True)

    if failed:
        sys.exit(1)
