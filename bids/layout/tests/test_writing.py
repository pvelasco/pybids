import pytest
import os
import shutil
from os.path import join, exists, islink, dirname

from bids import BIDSLayout
from bids.layout import BIDSFile
from bids.layout.writing import build_path
from bids.tests import get_test_data_path


@pytest.fixture
def writable_file(tmpdir):
    testfile = 'sub-03_ses-2_task-rest_acq-fullbrain_run-2_bold.nii.gz'
    fn = tmpdir.mkdir("tmp").join(testfile)
    fn.write('###')
    return BIDSFile(os.path.join(str(fn)))


@pytest.fixture(scope='module')
def tmp_bids(tmpdir_factory):
    tmp_bids = tmpdir_factory.mktemp("tmp_bids")
    yield tmp_bids
    shutil.rmtree(str(tmp_bids))
    # Ugly hack
    shutil.rmtree(join(get_test_data_path(), '7t_trt', 'sub-Bob'),
                  ignore_errors=True)


@pytest.fixture(scope='module')
def layout(tmp_bids):
    orig_dir = join(get_test_data_path(), '7t_trt')
    # return BIDSLayout(data_dir, absolute_paths=False)
    new_dir = join(str(tmp_bids), 'bids')
    os.symlink(orig_dir, new_dir)
    return BIDSLayout(new_dir)


class TestWritableFile:

    def test_build_path(self, writable_file):
        writable_file.entities = {
            'task': 'rest',
            'run': 2,
            'subject': '3'
        }

        # Single simple pattern
        with pytest.raises(TypeError):
            build_path(writable_file.entities)
        pat = join(writable_file.dirname,
                   '{task}/sub-{subject}/run-{run}.nii.gz')
        target = join(writable_file.dirname, 'rest/sub-3/run-2.nii.gz')
        assert build_path(writable_file.entities, pat) == target

        # Multiple simple patterns
        pats = ['{session}/{task}/r-{run}.nii.gz',
                't-{task}/{subject}-{run}.nii.gz',
                '{subject}/{task}.nii.gz']
        pats = [join(writable_file.dirname, p) for p in pats]
        target = join(writable_file.dirname, 't-rest/3-2.nii.gz')
        assert build_path(writable_file.entities, pats) == target

        # Pattern with optional entity
        pats = ['[{session}/]{task}/r-{run}.nii.gz',
                't-{task}/{subject}-{run}.nii.gz']
        pats = [join(writable_file.dirname, p) for p in pats]
        target = join(writable_file.dirname, 'rest/r-2.nii.gz')
        assert build_path(writable_file.entities, pats) == target

        # Pattern with conditional values
        pats = ['{task<func|acq>}/r-{run}.nii.gz',
                't-{task}/{subject}-{run}.nii.gz']
        pats = [join(writable_file.dirname, p) for p in pats]
        target = join(writable_file.dirname, 't-rest/3-2.nii.gz')
        assert build_path(writable_file.entities, pats) == target

        # Pattern with valid conditional values
        pats = ['{task<func|rest>}/r-{run}.nii.gz',
                't-{task}/{subject}-{run}.nii.gz']
        pats = [join(writable_file.dirname, p) for p in pats]
        target = join(writable_file.dirname, 'rest/r-2.nii.gz')
        assert build_path(writable_file.entities, pats) == target

        # Pattern with optional entity with conditional values
        pats = ['[{task<func|acq>}/]r-{run}.nii.gz',
                't-{task}/{subject}-{run}.nii.gz']
        pats = [join(writable_file.dirname, p) for p in pats]
        target = join(writable_file.dirname, 'r-2.nii.gz')
        assert build_path(writable_file.entities, pats) == target

        # Pattern with default value
        pats = ['sess-{session|A}/r-{run}.nii.gz']
        assert build_path({'run': 3}, pats) == 'sess-A/r-3.nii.gz'

        # Pattern with both valid and default values
        pats = ['sess-{session<A|B|C>|D}/r-{run}.nii.gz']
        assert build_path({'session': 1, 'run': 3}, pats) == 'sess-D/r-3.nii.gz'
        pats = ['sess-{session<A|B|C>|D}/r-{run}.nii.gz']
        assert build_path({'session': 'B', 'run': 3}, pats) == 'sess-B/r-3.nii.gz'

    def test_strict_build_path(self):

        # Test with strict matching--should fail
        pats = ['[{session}/]{task}/r-{run}.nii.gz',
                't-{task}/{subject}-{run}.nii.gz']
        entities = {'subject': 1, 'task': "A", 'run': 2}
        assert build_path(entities, pats, True)
        entities = {'subject': 1, 'task': "A", 'age': 22}
        assert not build_path(entities, pats, True)

    def test_build_file(self, writable_file, tmp_bids, caplog):
        writable_file.entities = {
            'task': 'rest',
            'run': 2,
            'subject': '3'
        }

        # Simple write out
        new_dir = join(writable_file.dirname, 'rest')
        pat = join(writable_file.dirname,
                   '{task}/sub-{subject}/run-{run}.nii.gz')
        target = join(writable_file.dirname, 'rest/sub-3/run-2.nii.gz')
        writable_file.copy(pat)
        assert exists(target)

        # Conflict handling
        with pytest.raises(ValueError):
            writable_file.copy(pat)
        with pytest.raises(ValueError):
            writable_file.copy(pat, conflicts='fail')
        writable_file.copy(pat, conflicts='skip')
        log_message = caplog.records[0].message
        assert log_message == 'A file at path {} already exists, ' \
                              'skipping writing file.'.format(target)
        writable_file.copy(pat, conflicts='append')
        append_target = join(writable_file.dirname,
                             'rest/sub-3/run-2_1.nii.gz')
        assert exists(append_target)
        writable_file.copy(pat, conflicts='overwrite')
        assert exists(target)
        shutil.rmtree(new_dir)

        # Symbolic linking
        writable_file.copy(pat, symbolic_link=True)
        assert islink(target)
        shutil.rmtree(new_dir)

        # Using different root
        root = str(tmp_bids.mkdir('tmp2'))
        pat = join(root, '{task}/sub-{subject}/run-{run}.nii.gz')
        target = join(root, 'rest/sub-3/run-2.nii.gz')
        writable_file.copy(pat, root=root)
        assert exists(target)

        # Copy into directory functionality
        pat = join(writable_file.dirname, '{task}/')
        writable_file.copy(pat)
        target = join(writable_file.dirname, 'rest', writable_file.filename)
        assert exists(target)
        shutil.rmtree(new_dir)


class TestWritableLayout:

    def test_write_files(self, tmp_bids, layout):

        tmpdir = str(tmp_bids)
        pat = join(str(tmpdir), 'sub-{subject<02>}'
                                '/sess-{session}'
                                '/r-{run}'
                                '/suffix-{suffix}'
                                '/acq-{acquisition}'
                                '/task-{task}.nii.gz')
        layout.copy_files(path_patterns=pat)
        example_file = join(str(tmpdir), 'sub-02'
                                         '/sess-2'
                                         '/r-1'
                                         '/suffix-bold'
                                         '/acq-fullbrain'
                                         '/task-rest.nii.gz')
        example_file2 = join(str(tmpdir), 'sub-01'
                                          '/sess-2'
                                          '/r-1'
                                          '/suffix-bold'
                                          '/acq-fullbrain'
                                          '/task-rest.nii.gz')

        assert exists(example_file)
        assert not exists(example_file2)

        pat = join(str(tmpdir), 'sub-{subject<01>}'
                                '/sess-{session}'
                                '/r-{run}'
                                '/suffix-{suffix}'
                                '/task-{task}.nii.gz')
        example_file = join(str(tmpdir), 'sub-01'
                                         '/sess-2'
                                         '/r-1'
                                         '/suffix-bold'
                                         '/task-rest.nii.gz')
        # Should fail without the 'overwrite' because there are multiple
        # files that produce the same path.
        with pytest.raises(ValueError):
            layout.copy_files(path_patterns=pat)
        try:
            os.remove(example_file)
        except OSError:
            pass
        layout.copy_files(path_patterns=pat, conflicts='overwrite')
        assert exists(example_file)

    def test_write_contents_to_file(self, tmp_bids, layout):
        contents = 'test'
        entities = {'subject': 'Bob', 'session': '01'}
        pat = join('sub-{subject}/sess-{session}/desc.txt')
        layout.write_contents_to_file(entities, path_patterns=pat,
                                      contents=contents)
        target = join(str(tmp_bids), 'bids', 'sub-Bob/sess-01/desc.txt')
        assert exists(target)
        with open(target) as f:
            written = f.read()
        assert written == contents
        assert target not in layout.files

    def test_write_contents_to_file_defaults(self, tmp_bids, layout):
        contents = 'test'
        entities = {'subject': 'Bob', 'session': '01', 'run': '1',
                    'suffix': 'bold', 'task': 'test', 'acquisition': 'test',
                    'bval': 0}
        layout.write_contents_to_file(entities, contents=contents)
        target = join(str(tmp_bids), 'bids', 'sub-Bob', 'ses-01',
                      'func', 'sub-Bob_ses-01_task-test_acq-test_run-1_bold.nii.gz')
        assert exists(target)
        with open(target) as f:
            written = f.read()
        assert written == contents

    def test_build_file_from_layout(self, tmpdir, layout):
        entities = {'subject': 'Bob', 'session': '01', 'run': '1'}
        pat = join(str(tmpdir), 'sub-{subject}'
                   '/sess-{session}'
                   '/r-{run}.nii.gz')
        path = layout.build_path(entities, path_patterns=pat)
        assert path == join(str(tmpdir), 'sub-Bob/sess-01/r-1.nii.gz')

        data_dir = join(dirname(__file__), 'data', '7t_trt')
        filename = 'sub-04_ses-1_task-rest_acq-fullbrain_run-1_physio.tsv.gz'
        file = join('sub-04', 'ses-1', 'func', filename)
        path = layout.build_path(file, path_patterns=pat)
        assert path.endswith('sub-04/sess-1/r-1.nii.gz')
