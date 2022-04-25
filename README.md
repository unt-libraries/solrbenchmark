# solrbenchmark

Python tools for benchmarking Solr instances: generating and loading fake but realistic data, running tests, and logging results.

## Installation

Currently this project lives only in our private GitLab instance, so getting it installed requires two things: setting up your GitLab authentication method, and knowing the secret incantation to get pip to install a package from a git repository.

### Set up SSH Authentication

[Set up an SSH key on your system and upload the public key to GitLab](https://content.library.unt.edu/help/ssh/index.md).

### OR Set up a Personal Access Token

[Create or obtain a personal access token](https://content.library.unt.edu/help/user/profile/personal_access_tokens.md) for this project that gives you the `read_repository` permission (at least).

Then configure git to use your access token wherever it encounters an SSH URL for this GitLab instance:

```bash
git config --global url."https://gitlab_username:gitlab_access_token@content.library.unt.edu".insteadOf "ssh://git@content.library.unt.edu"
```

- Replace `gitlab_username` with your GitLab username, and replace `gitlab_access_token` with your access token.
- This may seem a little roundabout, but it comes in handy when a project has other dependencies in the same repository. In fact, this project depends on `solrfixtures`, which also (currently) lives only in this repository. Git automatically performs the subsituttion for all applicable dependencies.

### Install as an Editable Project

```bash
pip install -e "git+ssh://git@content.library.unt.edu/utilities/pypackages/solrbenchmark.git@main#egg=solrbenchmark" --src /home/username/git-dependencies
```

- Substitute `@main` with whatever branch or tag you want to install.
- `#egg=solrbenchmark` defines the local name used for this package — recommended to leave as-is.
- `--src /path` is optional but [lets you define where to put the source files for the project](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-src).
- It may not be necessary to install it as editable with `-e`, but this seems like a good idea when using a non-release or between-release version.

### OR Install the Appropriate Package

*To Be Completed*


## Usage

The `solrbenchmark` package is a toolkit containing components that will help you benchmark a Solr core or collection. Before getting started you'll want to set up your benchmarking project using an environment with access to some non-production Solr instance. (Tests in the `tests/` directory use Docker to run the Solr instance and `pysolr` for the Python interface, for example. What you use to run Solr depends on what you're testing for — Docker could work fine for doing comparisons using different JVM settings or having different amounts of memory allocated. Or if you want to benchmark a live setup you'll want a Solr instance that mirrors that environment.)

### Example

```python
import pysolr

from solrbenchmark import docs, schema, terms, runner
from solrfixtures.emitters import choice, fixed, text
from solrfixtures.profile import Field

from .config import solrconn


# ****SETUP

# First, create a schema.
myschema = schema.BenchmarkSchema(
    Field('id', ... ),
    Field('title_display', ... ),
    SearchField('title_search', ... ),
    FacetField('title_facet', ... ),
    Field('author_display', ... ),
    SearchField('author_search', ... ),
    FacetField('author_facet', ... ),
    ...
)

# Generate a set of search terms and an emitter to emit them.
alphabet = text.make_alphabet([(ord('a'), ord('z'))])
word_em = text.Word(
    choice.poisson_choice(range(2, 11), mu=4),
    choice.Choice(alphabet)
)
term_em = terms.make_search_terms_and_emitter(word_em, num_vocab_words=50)

# Prepare the schema for a test set of 500,000 documents.
myschema.configure_search_term_injection(term_em)
myschema.build_facet_values_for_docset(500000)

# Create your document set.
# You have three choices here:
# 1. Generate your document set from scratch; do NOT save to disk.
docset = docs.TestDocSet.from_schema(myschema, 500000)

# 2. OR, generate your document set from scratch and stream it to a
#    file on your disk. Later you can recreate your document set from
#    this file.
fileset = docs.FileSet('/home/myuser/scratch/solrbenchmarking', 'mytest1')
docset = docs.TestDocSet.from_schema(myschema, 500000, fileset)

# 3. OR, recreate a document set from a previously saved file.
fileset = docs.FileSet('/home/myuser/scratch/solrbenchmarking', 'mytest1')
docset = docs.TestDocSet.from_fileset(fileset)

# Note: At this stage your documents don't yet exist in memory -- you
# get them via the `dset.docs` generator, and they are either created,
# created and saved to disk, or read from disk one at a time. Generally
# this will happen as they are indexed.


# ****BENCHMARK TESTS

# Before running tests, set up a log object for tracking your tests,
# recording metadata about what you're testing, and compiling stats, as
# well as a test runner for running your tests.
mylog = runner.BenchmarkTestLog(
    'mytest1',
    solr_version='8.11.1',
    solr_caches='caching disabled',
    solr_schema='my_test_schema, using docValues for facets',
    os='Docker on Windows WSL2/Ubuntu'
    os_memory='16gb',
    jvm_memory='-Xms52M -Xmx410M',
    jvm_settings='...',
    collection_size='500,000 docs / 950mb',
    notes='This is testing ...'
)
myrunner = runner.BenchmarkTestRunner(docset, mylog, solrconn)

# Index your documents. (Indexing timings are recorded.) You can choose
# a batch size and whether you want to keep track of commit timings, on
# a per-batch basis.
myrunner.index_docs(batch_size=1000, track_commits=True)

# Run search query tests. You can choose which sets of terms to include
# for which tests, how to label them, additional search args to use,
# (e.g. facets, fq limits, etc.) whether to repeat each search and take
# the average time, and whether to ignore the first N searches.
1word_terms = [t for t in term_em.items if ' ' not in t]
2word_terms = [t for t in term_em.items if len(t.split(' ') == 2)]
3word_terms = [t for t in term_em.items if len(t.split(' ') == 3)]
myrunner.run_searches(1word_terms, '1-word terms, no facets, no repeat')
myrunner.run_searches(2word_terms, '2-word terms, no facets, no repeat')
myrunner.run_searches(3word_terms, '3-word terms, no facets, no repeat')


# ****REPORTING

# After you've run a set of tests, you can save the output to a json
# file and compile a report, which returns all collected statistics as
# data dictionary. When compiling a report, you supply sets of
# aggregate groupings of the individual search tests you've run to
# create combined stats for those groups of tests.
myrunner.save_to_json_file('/home/myuser/scratch/mytest1_results.json')
report_data = myrunner.compile_report({
    '1-word terms': ['1-word terms, no facets, no repeat'],
    '2-word terms': ['2-word terms, no facets, no repeat'],
    '3-word terms': ['3-word terms, no facets, no repeat'],
    'all searches without facets': [
        '1-word terms, no facets, no repeat',
        '2-word terms, no facets, no repeat',
        '3-word terms, no facets, no repeat'
    ]
})

# From here e.g. saving your report data as a CSV or loading it into
# any number of analysis tools should be trivial. You'll of course also
# probably want to repeat your benchmark tests a number of times using
# different Solr configurations so you can compare timings. Ultimately
# what metadata you store in your log, how you store / organize your
# saved data, and how you label your tests is all up to you. The goal
# is to have reproducibility.
```


### Your BenchmarkSchema

The example above glosses over creation of the schema. This should be a `solrbenchmark.schema.BenchmarkSchema` object created using `solrfixtures.Field`-like objects that reflect fields in the schema for the Solr collection you're benchmarking. (You may need to do some profiling of your Solr collection to help you configure your BenchmarkSchema.)

  - Use `solrbenchmark.schema.SearchField` objects for the Solr fields you're going to want to search against while running tests. Each of these will have search terms from a controlled list injected so you'll get predictable results.
  - Use `solrbenchmark.schema.FacetField` objects for the Solr fields you'll want to facet against. Each of these will have sets of facet terms generated based on cardinality you can configure for each. (I.e., how many unique facet terms for each field.)
  - Use `solrfixture.Field` objects to populate fields you aren't querying against but still need to represent.


## Contributing

### Install for Development

Set up your SSH key or personal access token as [described above](#installation), and then:

```bash
git clone git+ssh://git@content.library.unt.edu/utilities/pypackages/solrbenchmark solrbenchmark
```

#### Poetry

This project uses [Poetry](https://python-poetry.org/) for builds and dependency management. You don't *have* to install it system-wide if you don't want to; I'm relatively new to Poetry myself and prefer to isolate it within each virtual environment that needs it instead of using a global Poetry instance to manage my virtual environments. In part this is because I also use tox.

#### Tox

[Tox](https://tox.wiki/en/latest/) is useful for testing against multiple versions of Python. Just like Poetry, I prefer to isolate tox within a virtual environment rather than installing it system wide. (What can I say, I have commitment issues.)

#### My Setup

Disclaimer: Python environment and dependency management is notoriously insane. I make no claims that my setup is _objectively_ good, but it works well for me, and it informs how the projects I maintain were built. Obviously this is not the only way to do it.

This is all about keeping components as isolated as possible so that nothing is hardwired and I can switch things out at will. Since both tox and Poetry can be used to manage virtual environments, this is the best way I've found to ensure they play well together. I've been quite happy with using pyenv + pyenv-virtualenv as my version / environment manager.

1. Install and configure [pyenv](https://github.com/pyenv/pyenv).
2. Install and configure [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv).
3. Use pyenv to download and install the currently supported Python versions, e.g. 3.7 to 3.10. (`pyenv install 3.7.13`, etc.)
4. For a project like solrbenchmark, I use pyenv-virtualenv to create my development environment with the latest Python version: `pyenv virtualenv 3.10.4 solrbenchmark-3.10.4`.
5. `cd` into the local repository root for this project and activate that virtualenv: `pyenv activate solrbenchmark-3.10.4`.
6. Do `pip install poetry`. (This installs Poetry into that virtualenv _only_.)
7. Do `poetry lock` to resolve dependencies and generate a `poetry.lock` file.
    - *Important*: The `solrbenchmark` project depends on the `solrfixtures` project, which currently lives only in this GitLab repository. In order for Poetry to resolve that dependency, it needs to be able to authenticate. If you're using the SSH key authentication method for this repository *and you have a passcode on your SSH key*, then you must run both this step and the next in an `ssh-agent` bash shell with your key loaded. Otherwise, Poetry will hang while it's trying to resolve dependencies.
8. Do `poetry install -E test` to install dependencies, including those needed for tests.

Now your dev virtual environment is all ready to go. As long as `solrbenchmark-3.10.4` is activated, you can use Poetry commands to manage dependencies and run builds; Poetry knows to install things to that environment.

But what if you want to develop against a different Python version? Just deactivate your environment (`pyenv deactivate`) and run through steps 4-8 again, substituting a different base Python in step 4, like `pyenv virtualenv 3.7.13 solrbenchmark-3.7.13`. Creating and configuring a new virtualenv takes just a minute or two. With the setup operationalized via `pyproject.toml` and Poetry, virtual environments are largely disposable.

And tox fits well into this workflow, since it automates this in its own way. Each time you run tox, it automatically builds the necessary virtual environments — one for each version of Python specified, plus additional ones for linting etc. (as applicable). All you have to do is expose all the binaries on the path you need to run, and tox will automatically pick up the correct binary for each environment it's told to create. Since pyenv lets you activate multiple Python versions at once in a way that tox recognizes, it works perfectly for this — ANY of the base Python versions or virtualenvs you have installed via pyenv can serve as the basis for tox's environments.

The added setup needed for tox is minimal:

1. You do need to have an environment with tox installed. Although you can do it system-wide, I prefer to create a virtualenv just for tox. I always use the latest version of Python (e.g., currently `tox-3.10.4`).
2. Activate the new virtualenv and do `pip install tox`. (Nothing else.)
3. Now, in your project repository root (for solrbenchmark), create a file called `.python-version`. Add all of the Python versions you want to use, 3.7 to 3.10. For 3.10, use your new `tox-3.10.4`. This should look something like this:
    ```
    3.7.13
    3.8.13
    3.9.11
    tox-3.10.4
    ```
4. Issue a `pyenv deactivate` command so that pyenv picks up what's in the file. (A manually-activated environment overrides anything set in a `.python-version` file.)
5. At this point you should have all four environments active at once in that directory. You can issue commands that run using binaries from any of those versions, and they will run correctly. For commands that multiple environments share, like `python`, the one for the first Python version listed is what runs. In other words — if you run `python` or `python3.7` then you'll get a 3.7.13 shell. If you run `python3.9` you'll get the 3.9.11 shell. When you run `tox`, the tox in your `tox-3.10.4` environment will run. But — even though tox only lives in that one virtual environment, because you have these various other Python base versions exposed this way, tox finds and picks the correct one for each environment it's configured to generate. You can even configure multiple environments set to run against the same Python version, such as if you separately want to test the set of minimum and maximum dependency versions for each Python.

So, in my workflow, I tend to develop using an environment like `solrbenchmark-3.10.4`, from earlier. As I work, I generally just run individual tests against the one environment, issuing the appropriate `pytest` command. Then, when I've finished some unit of work — usually before a commit — I use tox to run linters plus the full suite of tests. 99% of the time you won't have errors in earlier Python versions that don't show up when testing against your dev environment, so there's no need to take the extra time to run the full tox suite more often than that. (Admittedly sometimes I run it even less frequently.)

```bash
$ pyenv activate solrbenchmark-3.10.4  # Toggle a dev virtualenv ON.
# ...                                    Work on the project.
$ pytest tests/test_something.py -x    # Run specific tests against 3.10.4.
# ...                                    Continue developing / running tests.
$ pyenv deactivate                     # When ready for tox, Toggle dev OFF.
$ tox -e flake8                        # Run flake8. Fix errors until this passes.
$ tox -e pylint_critical               # Run critical pylint tests. Fix.
$ tox -e mypy                          # Run mypy tests. Fix.
$ tox                                  # Run ALL tox tests. Fix.
$ git add .
$ git commit
# etc.
```

Further, the tox / multi-Python setup above works for ANY projects on a given machine, as long as you create that `.python-version` file in the project root. You don't even have to create different virtualenvs for tox — that is, until you want to upgrade a project to a different Python version, at which point you may need to use multiple `tox-` environments if different projects need different 3.10 versions.

And this illustrates the only "painful" part of this workflow: managing entropy over time. As new Python versions come out, it's simple enough to update pyenv, install the new versions, and create new virtual environments. You just have to be systematic about managing things, _especially_ with multiple projects. E.g., you can't remove a Python version from your system entirely until you've updated all your projects to use the newer version, so over time you may end up with a lot of different Python versions installed, with different projects using different versions. As long as you label your virtualenvs with the version of Python they use (as above) you can at least see what's being used where. (I suspect this is a pain point with *any* workflow.)

### Tests

#### Docker and docker-solr

Since `solrbenchmark` requires Solr, some tests require an active Solr instance. For this I've supplied configuration to run Solr over Docker using [the official docker-solr image](https://github.com/docker-solr/docker-solr).

First, [download and install Docker](https://www.docker.com/get-started/) if you don't already have it.

##### Optional Configuration

If necessary, you can create a `tests/.env` file to configure the following options.

- `SOLR_HOST` — Defines what host to bind Solr to. Default is 127.0.0.1. (You shouldn't have to change this.)
- `SOLR_PORT` — Defines the host port on which to expose Solr. Default is :8983. Change this if there is a port conflict.

By default, when you run Solr, you can access the admin console at `localhost:8983`.

##### Running `docker-solr`

Launch `docker-solr` like this:

```bash
$ cd tests
$ ./docker-compose.sh up -d
```

The first time you run it, it will pull down the Solr image, which may take a few minutes. Also, note that you can leave off the `-d` to run Solr in the foreground, if you want to see what Solr is logging.

##### Stopping `docker-solr`

I generally launch my test Solr instance once when I start a work session and then just leave it running so I can test against it. When I'm done with a work session, such as at the end of the day, I stop Solr, like this:

```bash
$ ./docker-compose.sh down
```

#### Running Tests

Make sure your test Solr instance is up and running on whatever host/port is set in your `.env` file (127.0.0.1:8983 by default).

Then:

```bash
$ pytest
```

If you've set up tox as [described above](#my-setup), you can run the full test suite using:

```bash
$ tox
```
