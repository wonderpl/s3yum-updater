import os
import shutil
import tempfile
import glob
import unittest
import mock
import yum
import createrepo
repoupdate = __import__('repoupdate-daemon')


PACKAGE_NAME = 's3yum-updater'


def _createrepo(path):
    mdconf = createrepo.MetaDataConfig()
    mdconf.directory = path
    mdgen = createrepo.MetaDataGenerator(mdconf)
    mdgen.doPkgMetadata()
    mdgen.doRepoMetadata()
    mdgen.doFinalMove()


def _openrepo(path, cachedir='.'):
    yumbase = yum.YumBase()
    yumbase.preconf.disabled_plugins = '*'
    yumbase.conf.cachedir = cachedir
    yumbase.repos.disableRepo('*')
    yumbase.add_enable_repo('local', baseurls=['file://' + path])
    return yumbase


class MockS3Bucket(object):
    def __init__(self, base):
        self.base = base

    def list(self, prefix):
        for filename in os.listdir(os.path.join(self.base, prefix)):
            yield MockS3Key(os.path.join(prefix, filename), self.base)

    new_key = get_key = lambda self, name: MockS3Key(name, self.base)


class MockS3Key(object):
    def __init__(self, name, base='.'):
        self.name = name
        self.path = os.path.join(base, name)

    get_contents_to_filename = lambda self, filename: shutil.copyfile(self.path, filename)
    set_contents_from_filename = lambda self, filename: shutil.copyfile(filename, self.path)
    delete = lambda self: os.remove(self.path)


class RepoUpdateTestCase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.repo = 'noarch'
        self.repopath = os.path.join(self.tmpdir, self.repo)
        os.mkdir(self.repopath)
        rpmfile = glob.glob('dist/noarch/' + PACKAGE_NAME + '*.rpm')[-1]
        shutil.copyfile(rpmfile, os.path.join(self.repopath, 'i.rpm'))
        _createrepo(self.repopath)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_update_repodata(self):
        try:
            rpmfile = glob.glob('dist/noarch/' + PACKAGE_NAME + '*.rpm')[0]
        except IndexError:
            raise Exception('No rpm package found')
        else:
            shutil.copyfile(rpmfile, os.path.join(self.repopath, 'test.rpm'))

        with mock.patch('boto.auth.get_auth_handler'):
            with mock.patch('boto.s3.connection.S3Connection.head_bucket',
                            return_value=MockS3Bucket(self.tmpdir)):
                options = type('Options', (object,), dict(bucket='local', keep=1))()
                repoupdate.update_repodata(self.repo, ['test.rpm'], options)

        repo = _openrepo(self.repopath, cachedir=os.path.join(self.tmpdir, 'ycache'))
        self.assertTrue(repo.pkgSack.searchNames([PACKAGE_NAME]))


if __name__ == '__main__':
    unittest.main()
