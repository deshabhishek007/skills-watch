"""Skill extraction and alias normalisation against the real taxonomy."""


def test_alias_maps_to_canonical(taxonomy):
    assert taxonomy.extract("Experience with Amazon Web Services required") == ["AWS"]
    assert taxonomy.extract("We run on GCP and K8s") == ["Google Cloud", "Kubernetes"]


def test_alias_and_canonical_not_double_counted(taxonomy):
    skills = taxonomy.extract("Kubernetes experience; K8s certification a plus")
    assert skills == ["Kubernetes"]


def test_repeated_mentions_count_once(taxonomy):
    skills = taxonomy.extract("PHP PHP PHP and more PHP")
    assert skills == ["PHP"]


def test_word_boundaries(taxonomy):
    # "goal" must not match Go; "Java" must not fire inside JavaScript
    assert taxonomy.extract("Our goal is quality in everything") == []
    assert taxonomy.extract("Strong JavaScript skills") == ["JavaScript"]
    assert "Java" not in taxonomy.extract("JavaScript and TypeScript only")


def test_case_sensitive_acronyms(taxonomy):
    assert taxonomy.extract("let's go to the shop") == []
    assert taxonomy.extract("Backend services in Go") == ["Go"]
    assert taxonomy.extract("Golang microservices") == ["Go"]


def test_wordpress_stack(taxonomy):
    text = ("Senior WordPress Engineer: PHP 8, MySQL, Nginx, WooCommerce, "
            "WP-CLI, Cloudflare CDN, Linux servers")
    skills = taxonomy.extract(text)
    for expected in ["WordPress", "PHP", "MySQL", "Nginx", "WooCommerce",
                     "WP-CLI", "Cloudflare", "CDN", "Linux"]:
        assert expected in skills, f"missing {expected}"


def test_categories_assigned(taxonomy):
    assert taxonomy.category_of["WordPress"] == "WordPress"
    assert taxonomy.category_of["AWS"] == "Cloud"
    assert taxonomy.category_of["SEO"] == "Business"
