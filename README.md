solrbenchmark
=============

[![Build Status](https://github.com/unt-libraries/solrbenchmark/actions/workflows/do-checks-and-tests.yml/badge.svg?branch=main)](https://github.com/unt-libraries/solrbenchmark/actions)

- [About](#about)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)


## About

*`solrbenchmark`* contains tools for benchmarking Solr instances: generating and loading fake but realistic data, running tests, and reporting results.

Pinning down hardware and configuration requirements to run [Apache Solr](https://solr.apache.org/) can be notoriously difficult. So many factors affect how Solr will perform — including how many Solr cores or collections you have, the size and complexity of your schema(s), the size of your document sets, and the load you need to be able to handle. The usual advice is, to estimate your needs, you should profile for your specific use case.

One profiling approach is to benchmark — set up a Solr instance that reflects your production configuration (or your best guess about what a solid configuration would be), load up documents that reflect your use case, and run tests to measure baseline performance. Then run additional tests, each of which changes some configuration variable, and compare results against the baseline to see what changes have what effects.

Benchmarking in this manner is time consuming, and there's a lot to consider. I wrote this package in an effort to save myself (and possibly others) some time by documenting and operationalizing aspects of this process.

Be aware that this package was born from a particular test implementation and reflects numerous assumptions made during that testing process. However, my goal for this package has been to generalize that process enough to make it more widely useful. The decisions I made and parameters I used may be problematic in various ways, so I'm releasing this as a pre-production version, which I hope to refine in the future.

See the [Usage](#usage) section for more details.


### Requirements / Dependencies

Solrbenchmark requires Python 3 and is tested with Python versions 3.7 and above.

Other packages installed when you install `solrbenchmark` include `fauxdoc` ([more information here](https://github.com/unt-libraries/fauxdoc)) and `ujson`. If you're on Python 3.7, `importlib_metadata` and `typing_extentions` are installed as well.

You will of course also need access to a Solr instance to test, and you'll want to have an API for Solr in your Python environment: `pysolr` is what is expected and supported.

[Top](#top)


## Installation

You can install the latest published version of solrbenchmark with:

```
python -m pip install solrbenchmark
```

See [Contributing](#contributing) for the recommended installation process if you want to develop on solrbenchmark.

[Top](#top)


## Usage

### Before Getting Started

The `solrbenchmark` package is a toolkit containing components that will help you benchmark a Solr core or collection. Before getting started you'll want to set up your benchmarking project in an environment with access to the Solr instance(s) you want to use for testing. It's recommended to test against an isolated Solr instance. However, you could run tests against e.g. pre-production environments to help with stress testing and configuration. Running solrbenchmark tests against a live production Solr instance is *not* recommended.

You should also install the [`pysolr`](https://pypi.org/project/pysolr/) package in the same Python environment you install `solrbenchmark` to. When you run tests, it expects you to provide a Solr connection object that uses the `pysolr.Solr` API. (The methods it uses are limited to `add`, `commit`, and `search` — so if you have a different preferred Solr API, writing an adapter would not be too difficult. See `PysolrResultLike` and `PysolrConnLike` in `solrbenchmark.localtypes` for details about the expected protocols.)


### Considerations for Set Up and Configuration

Planning how you'll go about testing before getting started will help you understand the scope of your testing. The general goal is to emulate a realistic environment in a controlled way. Things to consider:

- **The document set you're going to test.**
    - Are you testing for an existing collection or a collection that doesn't exist yet? It's easier to model your test configuration after an existing collection; for a new collection, you'll have to do some guesswork.
    - How will you produce your test document set? With an existing collection, you can either use documents from the live document set or generate faked documents that emulate the live document set. With a new collection, clearly you'll *have* to generate faked documents.
        - Solrbenchmark assumes you will be generating faked documents — its tools are built around that use case. But, it could easily be adapted to use a pre-existing document set.
        - If you need to generate faked documents, you'll need to spend time setting up the code that will generate those documents. This process is somewhat involved. See [Setting Up Your Schema Faker](#setting-up-your-schema-faker) for more details.
    - How large do you need your test document set to be? Likely your test environment is a scaled-down version of your live environment. To get comparable tests, you'll want to scale your document set and your test environment similarly.
        - Memory usage is a particularly important consideration.
        - If you're using documents from your actual document set, you'll want a sample that's representative of the whole set, in terms of document characteristics. What exactly that means and how you approach that depends on your documents and their characteristics! If your test document set will be 10% the size of your real document set, then perhaps shuffling the documents and taking every 10th one is a good enough approach.
        - Do Solr requirements even scale linearly to document set size? To test this, you could create document sets of various sizes and test each against the same configurations to see how requirements scale.
- **The configurations you want to test.**
    - What will your baseline look like? It should be as close to your production configuration as possible. If you're testing a collection that isn't yet in production, or if you're using a scaled testing environment, then you'll have to make an educated guess about what a good middle-of-the-road configuration would look like for your collection.
    - What factors do you want to test? Brainstorm some variables you want to isolate and document some configurations that you want to test. Some good things to try to test include:
        - The amount of total OS memory available to Solr. (Running your test Solr instance in a VM or Docker container makes this easy to change.)
        - The amount of Java heap memory available to the JVM.
        - Other JVM settings that affect heap usage, garbage collection, etc.
        - Document set size. How do your Solr requirements scale as your document set grows?
        - Caches and cache sizes.
        - Schema variations. What happens if you implement certain fields (facets, sort fields, etc.) as DocValue fields versus inverted fields?
        - Query complexity. What happens when you run queries that include facet counts versus ones that don't? What happens when you run queries against portions of the document set (e.g. using an `'fq'` parameter)?
        - Solr version. If you're going to be upgrading to a new version of Solr, you can compare your current version to the new version to see how it will affect performance and what you might need to tweak.
    - In general, consider how you'll control for caching, since caching has a big impact on performance.
        - If you want tests that eliminate caching as much as possible, you can disable the Solr caches in your solrconfig.xml and run tests that fire each search only one time.
        - If you want tests that *only* test caching, you can enable Solr caches in your solrconfig.xml and run tests that fire each search multiple times and ignore the first N responses.
        - If you want tests that incorporate both uncached and cached searches, you can run tests that fire each search multiple times and average the results.
- **How will you switch your Solr configuration for each test?**
    - Switching Solr configurations over and over for different tests can take a lot of time. Consider ways you can automate this or otherwise make it more efficient. For instance, if you're testing a finite set of variations in your schema and solrconfig.xml, you could set up a Solr core for each variation and switch between cores for each applicable test.
    - I've found that running Solr in Docker is a good way to change otherwise hard-to-change factors, such as the amount of memory dedicated to the OS and the version of Solr you're testing against.
- **Test parameters.**
    - Do you want to test indexing performance? Search performance? Both?
    - For search tests, you'll need to consider what search terms you want to test and what other query parameters you want to test in combination, such as facet values.
        - For search terms, we assume that you want tests that cover a range of searches — searches on common terms that will give you a large result set down to rare terms and phrases that give you smaller results sets. Generally we assume that these search terms will appear in your document set in a ~normal distribution.
        - For facets, the two key factors are cardinality and distribution.
            - Cardinality: The set of unique values for each facet field in your document set should reflect the same cardinality you see in the actual collection — this could be static (5 unique values) or a function of the total number of documents (1 unique facet value per 1000 documents).
            - Distribution: Facet values probably occur in your actual document set along some kind of distribution curve — maybe a few appear very frequently, and there's a long tail where each only appears once. You probably want to replicate a similar distribution in your test document set.
        - If you are generating faked documents from scratch, you are probably generating random data, but you'll want to be able to generate predictable sets of search terms and facet terms — at least, ones that follow the necessary patterns — to go into your search and facet fields to produce the desired results. 
            - For search terms, the approach that `solrbenchmark` takes is to pre-generate a list of search terms for you and then embed those in the otherwise randomly generated search fields in your faked documents to give you a realistic distribution of results. You'll then use that list of search terms to run search tests.
            - Similarly, for facet terms, `solrbenchmark` generates a list of facet terms based on the target size for your document set (to produce the desired cardinality), and then it assigns facet values to documents to produce the desired distribution.
        - If your test document set instead samples from an existing real document set, you will need to conduct an analysis of your document set to determine what terms you want to search and what facet values you want to use in your testing.


### Setting Up Your Schema Faker

If you are generating a test document set that uses faked data, then you will need to devote time to configuring your schema faker. In part this will involve profiling certain aspects of the real data set that you're trying to emulate.
- Data types. Text for search fields, strings for facet fields, integers for integer fields, dates for date fields, etc.
- Approximate size and amount of data.
    - How much text appears in each text field, the sizes of facet strings, etc.
    - The range and distribution of values in multi-valued fields. How often is there 1 value? 2 values? 3? etc.
    - Occurrence of data in optional fields. Is a given field populated in 10% of records? 70%?
- Words and word-length distributions, especially for search fields. Your text doesn't necessarily have to reflect precise words or word distributions in a given language. But modeling appropriate distributions of word lengths isn't difficult.
    - (Side note: I'm not sure about this. What characteristics of text actually impact Solr performance? Presumably the number of words and word distributions *would* actually affect the size and contents of the search indexes. FUTURE TO-DO: Create a fauxdoc.Emitter type where we could generate a set vocabulary and the emitter would generate random text using the words in that vocabulary, instead of just randomly generating each word from scratch using individual alphabet letters.)
- Realistic distribution of search terms to test against. Completely random text won't cut it for terms you need to be able to search to produce realistically-sized results sets.
- Realistic cardinality and distribution of facet terms. Performance of faceting is known to be dependent on cardinality — how many unique facet values you have.

#### Emitters, Fields, and Schemas

The building blocks you'll use to create your schema faker are provided by `fauxdoc` and `solrbenchmark`. These include `Emitter` objects, which are then used in `Field` objects. A set of `Field` objects composes a `Schema` object, which you can then use to generate applicable documents. (See the [`fauxdoc` package](https://github.com/unt-libraries/fauxdoc) for more in-depth information about these.)

##### Emitters

These are the lowest-level objects that produce data values. The `fauxdoc` library contains the components for building your emitters, which includes compound emitters. Generally, you'll go through your Solr schema and create emitters that will emit data that reflects the "actual" data in whatever ways seem important.

In `solrbenchmark`, one new emitter type is added to the ones available in `fauxdoc`: `terms.TermChoice`. This is designed to help you emit search terms and facet terms in your document set so that:
1. Each term occurs at least once in your document set.
2. Terms otherwise follow a particular distribution.

##### Fields

As you create your emitters you will assign them to `Field` objects. There should be a one-to-one correspondence between your field instances and the fields in your actual Solr schema (not counting hidden field instances — see the note, below). For fields, you can assign chances that the field will be empty or not and define exactly how multiple values are generated.

In `solrbenchmark`, two new field types are added to the base `Field` type available in `fauxdoc`: `schema.SearchField` and `schema.FacetField`.
- `schema.SearchField` is what you should use for your search fields. It allows you to generate data normally but then to inject known search terms later.
- `schema.FacetField` is what you should use for your facet fields. It allows you to generate set lists of facet terms (based on the size of a document set) and distribute those values appropriately in your document set.
- For non-search, non-facet fields, you should use the base `Field` type.

Note: It isn't unusual to have groups of Solr fields that are related or dependent in some way. A group of fields might describe the same entity and so should always have the same number of values or should always all be populated or all be empty. To accomplish this, you can create a hidden field object that generates the larger entity, and then create not-hidden fields that pull data from the hidden field (using `fauxdoc.emitters.BasedOnFields` emitters).

##### Schema

Your `Schema` ultimately contains all of your fields and produces your document set for you. With `solrbenchmark`, a new class overrides the base `fauxdoc.profile.Schema` class: `schema.BenchmarkSchema`. This provides all of the functionality needed to configure and use your SearchFields and FacetFields.


### Usage Example

```python
import csv
from pathlib import Path

from fauxdoc.emitters import choice, fixed, fromfield, text
from fauxdoc.profile import Field
import pysolr
from solrbenchmark import docs, schema, terms, runner


# ****PLANNING & SETUP

# Let's assume you've done all the planning and setup discussed in the
# README.
#
# You'll want to create ConfigData objects with the metadata for the
# things you know you want to test.
#
# For instance, let's say we want to run tests comparing Java heap max
# 410M versus 820M versus 1230M.
config_heap_mx410 = runner.ConfigData(
    config_id='heap-mx410',
    solr_version='8.11.1',
    solr_caches='caching disabled',
    solr_schema='myschema, using docValues for facets',
    os='Docker on Windows WSL2/Ubuntu',
    os_memory='16GB',
    jvm_memory='-Xms52M -Xmx410M',
    jvm_settings='...',
    collection_size='500,000 docs @ 950mb',
)
config_heap_mx820 = config_heap_mx410.derive(
    'heap-mx820', jvm_memory='-Xms52M -Xmx820M'
)
config_heap_mx1230 = config_heap_mx410.derive(
    'heap-mx1230', jvm_memory='-Xms52M -Xmx1230M'
)

# We'll just use one docset containing 500,000 documents.
docset_id = 'myschema-500000'

# And we should go ahead and configure the location where we want to
# store files.
savepath = Path('/home/myuser/myschema_benchmarks/heap_tests/')

# Now we create our BenchmarkSchema, which reflects our Solr fields.
# Note: For fields where e.g. we have a display field, a facet field,
# and a search field that all use the same value, the facet field
# should always be the original source, as shown here. A facet field
# should never copy or be based on another field.
myschema = schema.BenchmarkSchema(
    Field('id', ... ),
    schema.FacetField('title_facet', ...),
    schema.FacetField('author_facet', ...),
    ),
    # etc.
)
myschema.add_fields(
    Field(
        'title_display',
        fromfield.CopyFields(myschema.fields['title_facet'])
    ),
    Field(
        'author_display',
        fromfield.CopyFields(myschema.fields['author_facet'])
    ),
    schema.SearchField(
        'title_search',
        fromfield.CopyFields(myschema.fields['title_facet'])
    ),
    schema.SearchField(
        'author_search',
        fromfield.CopyFields(myschema.fields['author_facet'])
    ),
    # etc.
)

# We generate a set of search terms and an emitter to emit them. We
# want terms to be ~realistic-ish lengths, so we use a Choice emitter
# with a poisson distribution to decide lengths, with 4-letter words
# being most populous.
alphabet = text.make_alphabet([(ord('a'), ord('z'))])
word_em = text.Word(
    # IMPORTANT: Below, why is `mu` 3 if we want 4-letter words to be
    # most populous? Because the range starts at 2, a *y-axis* value of
    # 3 corresponds with 4-letter words. (1 => 2-letter words, 2 => 3-
    # letter words, 3 => 4-letter words.)
    choice.poisson_choice(range(2, 11), mu=3),
    choice.Choice(alphabet)
)
term_em = terms.make_search_term_emitter(word_em, vocab_size=50)

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
# them via the `docset.docs` generator, and they are either created,
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
# are testing. How we do this largely depends on how our Solr instances
# are set up. If we're testing against one Solr instance, then we need
# to make sure we run one test, clear out Solr, change the heap size,
# restart Solr, and then run the next test. Although we could probably
# automate this using Docker, let's just create a function to run one
# test so we can do it manually.

def run_heap_test(solrconn, configdata, docset, search_defs):
    # We'll make this interactive so it's at least partly automated.
    print(f'STARTING {configdata.config_id} TESTS')
    print('Please (re)configure and (re)start Solr now.')
    input('(Press return when you are ready to run the test.)')
    print('')

    # We create a BenchmarkRunner object that will run our tests and
    # track statistics for us.
    testrunner = runner.BenchmarkRunner(solrconn)
    testrunner.configure(docset.id, configdata)

    # Now we just index our docset (indexing timings are recorded) ...
    print('Indexing documents.')
    testrunner.index_docs(docset, batch_size=1000, verbose=True)
    
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
    testrunner.save_log(docset.fileset.basepath)

    # And we can probably go ahead and clear Solr, unless there's any
    # additional looking / searching / testing we want to do before
    # running the next test.
    print('Cleaning up.')
    solrconn.delete(q='*:*', commit=True)
    print('Done.\n')
    # Returning the test runner object gives us access to all the recorded
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

[Top](#top)


## Contributing

### Installing for Development and Testing

Fork the project on GitHub and then clone it locally:

```bash
git clone https://github.com/[your-github-account]/solrbenchmark.git
```

All dependency and build information is defined in `pyproject.toml` and follows [PEP 621](https://peps.python.org/pep-0621/). From the solrbenchmark root directory, you can install it as an editable project into your development environment with:

```bash
python -m pip install -e .[dev]
```

The `[dev]` ensures it includes the optional development dependencies:
- `pytest`
- `pysolr`
- `python-dotenv`

Note that the last two development dependencies are only used for running integration tests.


### Running Tests

The repository and source package include both unit tests and integration tests, where the integration tests require an active Solr instance to test against. By default, if you invoke `pytest` from the repository root, both sets of tests will run.

#### Unit Tests

Run *only* unit tests in your active environment using:

```bash
pytest --ignore=tests/integration 
```

from the solrbenchmark root directory. Unit tests do *not* require a running Solr instance.

#### Integration tests

Integration tests and all configuration needed to run them are isolated in the `tests/integration` directory.

Before you run them, you must either provide your own test Solr core that uses the configuration in the `tests/integration/solrconf` directory or use Docker and docker-compose with the supplied configuration.

By default we expect Solr to run on 127.0.0.1:8983 using a core called `test_core`. You can change any of these values by setting them in a `tests/integration/.env` file, using `tests/integration/template.env` as a template. If the defaults are fine, you do not need to create the .env file.

**IMPORTANT** — The integration tests expect the test core to start out empty, and they will clear it out when they complete. DO NOT USE IT FOR ANYTHING OTHER THAN THESE TESTS.

##### Using Docker-solr

To use Docker, you must [have Docker and docker-compose installed](https://www.docker.com/get-started/). The supplied configuration will run Solr in Docker using [the official docker-solr image](https://github.com/apache/solr-docker).

By default, when you run Solr, you can access the admin console at `localhost:8983`.

Launch `docker-solr` like this:

```bash
$ cd tests/integration
$ ./docker-compose.sh up -d
```

The first time you run it, it will pull down the Solr image, which may take a few minutes. Also, note that you can leave off the `-d` to run Solr in the foreground, if you want to see what Solr logs as it runs.

If you've launched `docker-solr` using `-d`, you can stop it like this, assuming you're still in the `tests/integration` directory:

```bash
$ ./docker-compose.sh down
```

If it's running in the foreground, you can stop it with `ctrl+c`.

##### Running Integration Tests

Make sure your test Solr instance is up and running on whatever host/port is set in your `.env` file (127.0.0.1:8983 by default).

Then:

```bash
$ pytest -k integration
```

#### Tox

Because this is a library, it needs to be tested against all supported environments for each update, not just one development environment. The tool we use for this is [tox](https://tox.wiki/en/latest/).

Rather than use a separate `tox.ini` file, I've opted to put the tox configuration directly in `pyproject.toml` (under the `[tool.tox]` table). There, I've defined several environments: flake8, pylint, and each of py37 through py311 using both the oldest possible dependencies and newest possible dependencies. When you run tox, you can target a specific environment, a specific list of environments, or all of them.

When tox runs, it automatically builds each virtual environment it needs, and then it runs whatever commands it needs within that environment (for linting, or testing, etc.). All you have to do is expose all the necessary Python binaries on the path, and tox will pick the correct one. My preferred way to manage this is with [pyenv](https://github.com/pyenv/pyenv) + [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv).

For example: Install these tools along with the Python versions you want to test against. Then:

1. Create an environment with tox installed. E.g.:
    ```
    pyenv virtualenv 3.10.8 tox-3.10.8
    pyenv activate
    python -m pip install tox
    ```
2. In the project repository root, create a file called `.python-version`. Add all of the Python versions you want to use, e.g., 3.7 to 3.11. For 3.10, use your `tox-3.10.8`. This should look something like this:
    ```
    3.7.15
    3.8.15
    3.9.15
    tox-3.10.8
    3.11.0
    ```
4. If `tox-3.10.8` is still activated, issue a `pyenv deactivate` command so that pyenv picks up what's in the file. (A manually-activated environment overrides anything set in a `.python-version` file.)
5. At this point you should have all five environments active at once in that directory. When you run `tox`, the tox in your `tox-3.10.8` environment will run, and it will pick up the appropriate binaries automatically (`python3.7` through `python3.11`) since they're all on the path.

Now you can just invoke tox to run linters and all the tests against all the environments:

```bash
tox
```

Or just run linters:

```bash
tox -e flake8,pylint_critical,mypy_strict
```

Or run tests against a list of specific environments:

```bash
tox -e py39-oldest,py39-newest
```

Note that the default test environments only run unit tests. You can run integration tests from tox using `py37-integration`, `py38-integration`, etc. Integration tests, along with build commands, are not part of the default `tox` invocation. See the tox setup in the `tool.tox` section of the [pyproject.toml](pyproject.toml) file to find all available tox environments.

[Top](#top)


## License

See the [LICENSE](LICENSE) file.

[Top](#top)
