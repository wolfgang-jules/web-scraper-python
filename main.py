import argparse
from scraper import Scraper


def main():
    parser = argparse.ArgumentParser(description="Generic Scraper - runner")
    parser.add_argument('--config', type=str, default='config-verifone.json')
    args = parser.parse_args()
    scraper = Scraper(args.config)
    scraper.scrape()


if __name__ == '__main__':
    main()
