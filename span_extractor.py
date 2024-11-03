import json, argparse, logging, csv
from elasticsearch import Elasticsearch
from typing import Any, Dict, List, Tuple
from pprint import pprint
from slugify import slugify


class SpanExtractor:

    logger = logging.getLogger("SpanExtractor")

    # configurations = {
    #     "basic_auth": ("elastic", "elastic"),
    # }
    configurations = {
        "basic_auth": ("emalouang", "w61y8iw5"),
    }

    def __init__(self):

        # Create a handler
        handler = logging.StreamHandler()

        # Create a formatter that includes the logger name, file detail, and line number
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Set the formatter for the handler
        handler.setFormatter(formatter)

        # Add the handler to the logger
        self.logger.addHandler(handler)

        # Set the log level
        self.logger.setLevel(logging.INFO)

    def connect_to_elasticsearch(self) -> Elasticsearch:
        # es = Elasticsearch(
        #     hosts="http://localhost:9200/",
        #     **self.configurations,
        #     verify_certs=False,
        # )

        es = Elasticsearch(
            hosts="https://10.30.254.250:9200/",
            **self.configurations,
            verify_certs=False,
        )

        return es

    def match_columns_and_values(self, data):
        columns = [col["name"] for col in data["columns"]]
        values = data["values"]

        result = []
        for value in values:
            row_dict = dict(zip(columns, value))
            result.append(row_dict)

        return result

    def extract_entry_span(self, name: str, time_interval: str) -> Dict[str, Any]:
        # Placeholder for Elasticsearch query
        es = self.connect_to_elasticsearch()
        query = """
        FROM traces-apm* 
        | WHERE transaction.name == "{span_name}"
        | KEEP span.id, span.name, transaction.id, transaction.name, processor.event, trace.id, parent.id, @timestamp, service.name 
        | LIMIT 1 
        """.format(
            span_name=name
        )
        try:
            response = es.esql.query(
                query=query,
                format="json",
            )
            self.logger.info(response.body)
            pprint(response.body)
            entry_span = self.match_columns_and_values(response.body)
            self.logger.info(entry_span)
            pprint(entry_span)
            if len(entry_span) == 0:
                raise Exception("No entry span found")
            return entry_span[0]
        except Exception as e:
            self.logger.error(f"Failed to query Elasticsearch: {e}")
            raise e

    def extract_children_spans(self, span_id: str) -> List[Dict[str, Any]]:
        es = self.connect_to_elasticsearch()
        query = """
            FROM traces-apm* 
            | WHERE parent.id == "{span_id}" 
            | KEEP span.id, span.name, transaction.id, transaction.name, processor.event, trace.id, parent.id, @timestamp, service.name
            """.format(
            span_id=span_id
        )
        try:
            response = es.esql.query(
                query=query,
                format="json",
            )

            pprint(response.body)
            self.logger.info(response.body)
            children_spans = self.match_columns_and_values(response.body)
            self.logger.info(children_spans)
            return children_spans
        except Exception as e:
            self.logger.error(f"Failed to query Elasticsearch: {e}")
            raise e

    def get_span_pairs(
        self, span: Dict[str, Any]
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        span_pairs = []
        children_spans = self.extract_children_spans(span["span.id"])
        for child_span in children_spans:
            span_pairs.append((span, child_span))
            grand_children_pairs = self.get_span_pairs(child_span)
            span_pairs.extend(grand_children_pairs)
        return span_pairs

    def extract_values(self, data, output_file):
        result = []
        for pair in data:
            temp = []
            for item in pair:
                span_name = (
                    item["span.name"]
                    if item["span.name"] is not None
                    else item["transaction.name"]
                )
                processor_event = item["processor.event"]
                temp.append(
                    {"span.name": span_name, "processor.event": processor_event}
                )
            result.append((temp[0], temp[1]))

        with open(output_file, "w") as f:
            json.dump(result, f)
        return result

    def traversal(
        self, name: str, time_interval: str, output_file: str
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        entry_span = self.extract_entry_span(name, time_interval)
        span_pairs = self.get_span_pairs(entry_span)

        with open(output_file, "w") as f:
            json.dump(span_pairs, f)
        return span_pairs


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Process some value.")

    parser.add_argument(
        "-i",
        "--input",
        type=str,
        help="Output file where to save the result, an csv file",
    )
    args = parser.parse_args()
    extractor = SpanExtractor()
    with open(f"{args.input}", "r") as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            span_name = row[0]
            name_slug = slugify(span_name)
            global_ouput = f"{name_slug}_rawdata.json"
            detail_output = f"{name_slug}_spanonly.json"
            cleaned_output = f"{name_slug}_digraph.json"

            span_pairs = extractor.traversal(span_name, "", global_ouput)

            # with open("test.json", "r") as f:
            #     span_pairs = json.load(f)

            results = extractor.extract_values(span_pairs, detail_output)

            input = []
            for pair in results:
                temp = []
                parent_span_name = pair[0]["span.name"]
                child_span_name = pair[1]["span.name"]

                input.append((parent_span_name, child_span_name))

            with open(cleaned_output, "w") as f:
                json.dump(input, f)
