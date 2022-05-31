# solrbenchmark

Python tools for benchmarking Solr instances: generating and loading fake but realistic data, running tests, and reporting results.

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

The `solrbenchmark` package is a toolkit containing components that will help you benchmark a Solr core or collection. Before getting started you'll want to set up your benchmarking project using an environment with access to the Solr instance(s) you want to use for testing. The `pysolr` package is included as a base dependency for this project — it's expected you'll use this as the Python interface to the Solr API, even though it isn't invoked in the project code.

(The `tests/test_runner*` tests provide a basic example using Docker to run a Solr instance. How you actually run Solr depends on what you're testing for — Docker could work fine for doing comparisons using different JVM settings or having different amounts of memory allocated. Or if you want to benchmark a live setup you'll want a Solr instance that mirrors that environment.)

### Usage Example

```python
import csv
from pathlib import Path

import pysolr

from solrbenchmark import docs, schema, terms, runner
from solrfixtures.emitters import choice, fixed, fromfield, text
from solrfixtures.profile import Field


# ****PLANNING & SETUP

# There's some planning you'll want to do up front: what configurations
# do you want to test; how many documents do you need; do you need more
# than one document set; what kinds of tests are you going to run; etc.
#
# Consider building your metadata (identifiers to ID test components
# and configuration metadata) first. Obviously, you can change things
# later, but this gives you something to work with.
#
# Let's say we want to run tests comparing Java heap max 410M versus
# 820M versus 1230M.
config_heap_mx410 = runner.ConfigData(
    config_id='heap-mx410',
    solr_version='8.11.1',
    solr_caches='caching disabled',
    solr_schema='myschema, using docValues for facets',
    os='Docker on Windows WSL2/Ubuntu'
    os_memory='16GB',
    jvm_memory='-Xms52M -Xmx410M',
    jvm_settings='...',
    collection_size='500,000 docs @ 950mb',
    notes='Testing the effect of Java max heap size.'
)
config_heap_mx820 = config_heap_mx410.derive(
    'heap-mx820', jvm_memory='-Xms52M -Xmx820M'
)
config_heap_mx1230 = config_heap_mx410.derive(
    'heap-mx1230', jvm_memory='-Xms52M -Xmx1230M'
)

# We'll just have one docset of 500,000 documents.
docset_id = 'myschema-500000'

# And we should go ahead and configure the location where we want to
# store files.
savepath = Path('/home/myuser/myschema_benchmarks/heap_tests/')

# Now we create our BenchmarkSchema, which reflects our Solr fields.
# (If you use dynamic fields heavily, you'll have to know what fields
# are actually in your data and make a concrete schema that reflects
# whatever you have.)
myschema = schema.BenchmarkSchema(
    Field('id', ... ),
    Field('title_display', ... ),
    Field('author_display', ... ),
    # etc.
)
myschema.add_fields(
    SearchField('title_search',
                fromfield.CopyFields(myschema.fields['title_display'])),
    FacetField('title_facet',
                fromfield.CopyFields(myschema.fields['title_display'])),
    SearchField('author_search',
                fromfield.CopyFields(myschema.fields['author_display'])),
    FacetField('author_facet',
                fromfield.CopyFields(myschema.fields['author_display'])),
    # etc.
)

# We generate a set of search terms and an emitter to emit them. We
# want terms to be ~realistic-ish lengths, so we use a Choice emitter
# with a poisson distribution to decide lengths, with 4-letter words
# being most populous.
alphabet = text.make_alphabet([(ord('a'), ord('z'))])
word_em = text.Word(
    choice.poisson_choice(range(2, 11), mu=4),
    choice.Choice(alphabet)
)
term_em = terms.make_search_terms_and_emitter(word_em, vocab_size=50)

# We configure the schema for a test set of 500,000 documents.
myschema.configure(500000, term_em, term_doc_ratio=0.75, overwrite_chance=0.25)

# Next we set up the document set. We have three choices here:
# 1. Generate it from scratch; do NOT save to disk.
docset = docs.DocSet.from_schema(docset_id, myschema)

# 2. OR, generate it from scratch and stream it to a file. Later we can
#    recreate the document set from that file.
docset = docs.DocSet.from_schema(docset_id, myschema, savepath=savepath)

# 3. OR, recreate a document set from a previously saved session.
docset = docs.DocSet.from_disk(docset_id, savepath)

# Note: At this stage our documents don't yet exist in memory -- we get
# them via the `dset.docs` generator, and they are either created,
# created and saved to disk, or read from disk one at a time. Generally
# this will happen as they are indexed.

# The last thing to do before running tests is to decide exactly what
# searches we want to run that will fully test what we're trying to
# test. We can submit specific sets of terms to search in addition to
# any other args to send to Solr for each search run, so this is quite
# flexible. You can set this up however you want, but my preferred
# method is to create a data structure containing labels and parameters
# (i.e. terms and kwargs) for each search run.
terms_1word = [t for t in term_em.items if ' ' not in t]
terms_2word = [t for t in term_em.items if len(t.split(' ') == 2)]
title_facet_terms = myschema.fields['title_facet'].terms
all_facet_args = {
    'facet': 'true', 'facet.field': 'title_facet',
    'facet.field': 'author_facet'
}
search_defs = (
    ('1-word terms + no facets + no fq', terms_1word, {}),
    ('2-word terms + no facets + no fq', terms_2word, {}),
    ('1-word terms + all facets + no fq', terms_1word, ),
    ('2-word terms + all facets + no fq', terms_2word, all_facet_args),
    ('1-word terms + no facets + fq 1st title facet val', terms_1word, {
        'fq': f'title_facet:"{title_facet_terms[0]}"'
    }),
    ('2-word terms + no facets + fq 1st title facet val', terms_2word, {
        'fq': f'title_facet:"{title_facet_terms[0]}"'
    }),
    ('1-word terms + all facets + fq 1st title facet val', terms_1word,
     dict(all_facet_args, **{
        'fq': f'title_facet:"{title_facet_terms[0]}"'
     )
    }),
    ('2-word terms + all facets + fq 1st title facet val', terms_2word,
     dict(all_facet_args, **{
        'facet': 'true', 'facet.field': 'title_facet',
        'facet.field': 'author_facet'
        'fq': f'title_facet:"{title_facet_terms[0]}"'
     )
    }),
    # etc.
)
# We can also define some aggregate groupings of our searches, where we
# want combined stats reported, later. All we need to do is map new
# group labels to lists of search_def labels that belong to each group.
aggregate_groups = {
    'no facets GROUP': [d[0] for d in search_defs if '+ no facets ' in d[0]],
    'all facets GROUP': [d[0] for d in search_defs if '+ all facets ' in d[0]],
    '1-word terms GROUP': [d[0] for d in search_defs if d[0].startswith('1')],
    '2-word terms GROUP': [d[0] for d in search_defs if d[0].startswith('2')],
    # etc.
}


# ****RUNNING BENCHMARK TESTS & REPORTING

# Ultimately we want to run three tests, one for each JVM heap size we
# want to test. How we do this largely depends on how our Solr
# instances are set up. If we're testing against one Solr instance,
# then we need to make sure we run one test, clear out Solr, change the
# heap size, restart Solr, and then run the next test. Although we
# could probably automate this using Docker, let's just create a
# function to run one test so we can do it manually.

def run_heap_test(solrconn, configdata, docset, search_defs):
    # We'll make this interactive so it's at least partly automated.
    print(f'STARTING {configdata.config_id} TESTS')
    print('Please (re)configure and (re)start Solr now.')
    input('(Press return when you are ready to run the test.)')
    print('')

    # We create a BenchmarkRunner object that will run our tests and
    # track statistics for us.
    testrunner = runner.BenchmarkRunner(docset, configdata, solrconn)

    # Now we just index our docset (indexing timings are recorded) ...
    print('Indexing documents.')
    testrunner.index_docs(batch_size=1000, verbose=True)
    
    # ... and run the searches we've configured. Note the 'rep_n=5' and
    # 'ignore_n=1' parameters. This tells it to search each term 5
    # times in a row and ignore the qtime from the 1st. (The average of
    # the remaining 4 search qtimes is the qtime for that term/search.)
    print('Running searches.')
    for label, termset, qkwargs in search_defs:
        testrunner.run_searches(termset, label, rep_n=5, ignore_n=1,
                                verbose=True)

    # Generally we'll want to save the results of each test so we don't
    # have to repeat the test later.
    testrunner.log.save_to_json_file(docset.savepath)

    # And we can probably go ahead and clear Solr, unless there's any
    # additional looking / searching / testing we want to do before
    # running the next test.
    print('Cleaning up.')
    solrconn.delete('*:*', commit=True)
    print('Done.\n')
    # Returning the test log object gives us access to all the recorded
    # data.
    return testrunner.log


if __name__ == '__main__':
    solrconn = pysolr.Solr(url='http://localhost:8983/solr/myschema_core')
    print('Welcome to the benchmark test runner for Heap tests.\n')
    log_410 = run_heap_test(solrconn, config_heap_mx410, docset, search_defs)
    log_820 = run_heap_test(solrconn, config_heap_mx820, docset, search_defs)
    log_1230 = run_heap_test(solrconn, config_heap_mx1230, docset, search_defs)

    # The very last step is reporting. We can compile a final report
    # for each test, which is a data dictionary containing e.g. average
    # timings for indexing and searching, including whatever aggregate
    # groups we decided we need. From there we can convert those to
    # whatever format we want for analysis and comparison.
    csv_rows = []
    for tlog in (log_410, log_820, log_1230):
        report = tlog.compile_report(aggregate_groups)
        # This `report_to_csv` function doesn't exist; we'd have to
        # create it. We'd also want a header row. Or we could use
        # csv.DictWriter. How you do all of this just depends on what
        # data you want in your final report and how you want it
        # formatted.
        csv_rows.append(report_to_csv(report))
        # In addition, we can also get more detailed stats from each
        # test log object -- tlog.indexing_stats and tlog.search_stats,
        # if we want more detail than the compiled report provides.
    with open(savepath / 'final_report.csv', 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(csv_rows)
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
