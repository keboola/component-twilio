'''
kds-team.app-twilio

'''

import logging
import logging_gelf.handlers
import logging_gelf.formatters
import sys
import os
import json
from datetime import datetime  # noqa
from twilio.rest import Client
import pandas as pd
import csv

from kbc.env_handler import KBCEnvHandler
from kbc.result import KBCTableDef  # noqa
from kbc.result import ResultWriter  # noqa


# configuration variables
KEY_ACCOUNT_SID = 'account_sid'
KEY_AUTH_TOKEN = '#auth_token'
KEY_MESSAGING_SERVICE_SID = 'messaging_service_sid'
KEY_OUTPUT_LOG = 'output_log'

MANDATORY_PARS = [
    KEY_ACCOUNT_SID,
    KEY_AUTH_TOKEN,
    KEY_MESSAGING_SERVICE_SID,
    KEY_OUTPUT_LOG
]
MANDATORY_IMAGE_PARS = []

# Default Table Output Destination
DEFAULT_TABLE_SOURCE = "/data/in/tables/"
DEFAULT_TABLE_DESTINATION = "/data/out/tables/"
DEFAULT_FILE_DESTINATION = "/data/out/files/"
DEFAULT_FILE_SOURCE = "/data/in/files/"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s : [line:%(lineno)3s] %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S")

# Disabling list of libraries you want to output in the logger
disable_libraries = [
    'twilio',
    'twilio.http_client'
]
for library in disable_libraries:
    logging.getLogger(library).disabled = True

if 'KBC_LOGGER_ADDR' in os.environ and 'KBC_LOGGER_PORT' in os.environ:

    logger = logging.getLogger()
    logging_gelf_handler = logging_gelf.handlers.GELFTCPSocketHandler(
        host=os.getenv('KBC_LOGGER_ADDR'), port=int(os.getenv('KBC_LOGGER_PORT')))
    logging_gelf_handler.setFormatter(
        logging_gelf.formatters.GELFFormatter(null_character=True))
    logger.addHandler(logging_gelf_handler)

    # remove default logging to stdout
    logger.removeHandler(logger.handlers[0])

APP_VERSION = '0.0.3'


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        KBCEnvHandler.__init__(self, MANDATORY_PARS)
        """
        # override debug from config
        if self.cfg_params.get('debug'):
            debug = True
        else:
            debug = False

        self.set_default_logger('DEBUG' if debug else 'INFO')
        """
        logging.info('Running version %s', APP_VERSION)
        logging.info('Loading configuration...')

        try:
            self.validate_config()
            self.validate_image_parameters(MANDATORY_IMAGE_PARS)
        except ValueError as e:
            logging.error(e)
            exit(1)

    def get_tables(self, tables, mapping):
        """
        Evaluate input and output table names.
        Only taking the first one into consideration!
        mapping: input_mapping, output_mappings
        """
        # input file
        table_list = []
        for table in tables:
            name = table["full_path"]  # noqa
            if mapping == "input_mapping":
                destination = table["destination"]
            elif mapping == "output_mapping":
                destination = table["source"]
            table_list.append(destination)

        return table_list

    def send_message(self, phone, message_text):
        '''
        Sending out messages via Twilio
        '''
        try:
            message = self.twilio_client.messages.create(  # noqa
                body=message_text,
                messaging_service_sid=self.messaging_service_sid,
                to=phone
            )
            # logging.info("SMS sent: {0}".format(message.sid))
            return True
        except Exception as err:
            logging.error('Issue with SMS sent: {} - {}'.format(phone, err))
            return False

    def output_log_file(self, data_in):
        '''
        Outputting Logging File
        '''

        if len(data_in) > 0:
            data_df = pd.DataFrame(data_in)
            file_name = 'log.csv'
            file_name_path = DEFAULT_TABLE_DESTINATION + file_name

            if not os.path.isfile(file_name_path):
                data_df.to_csv(file_name_path, index=False)
                self.produce_manifest()
            else:
                data_df.to_csv(file_name_path, index=False,
                               header=False, mode='a')

    def produce_manifest(self):
        """
        Dummy function to return header per file type.
        """

        file = "/data/out/tables/log.csv.manifest"

        manifest = {
            "incremental": True,
            "primary_key": [
                "phone",
                "datetime"
            ]
        }

        try:
            with open(file, 'w') as file_out:
                json.dump(manifest, file_out)
                logging.info("Output manifest file produced.")
        except Exception as e:
            logging.error("Could not produce output file manifest.")
            logging.error(e)

    def validate_user_params(self, params, in_tables):
        '''
        Validating user input parameters
        '''

        # 1 - Check if the component is configured
        if params == {}:
            logging.error('Please configure your component.')
            sys.exit(1)

        # 2 - Ensure all credentials are enter
        if not params.get(KEY_ACCOUNT_SID) or not params.get(KEY_AUTH_TOKEN) \
                or not params.get(KEY_MESSAGING_SERVICE_SID):
            logging.error(
                'Please enter your credentials: [Account SID], [Authentication Token], [Messaging Service SID]')
            sys.exit(1)

        # 3 - Ensure at least one table is configured
        if len(in_tables) < 1:
            logging.error('Input tables are missing.')
            sys.exit(1)

        # 4 - Check if the input tables have the required columns
        required_columns = ['phone_number', 'message']
        for table in in_tables:
            with open(table['full_path']) as f:
                reader = csv.reader(f)
                headers = next(reader)
            f.close()

            for h in required_columns:
                if h not in headers:
                    logging.error(
                        f'[{table["destination"]}] is missing required column: {required_columns}')
                    sys.exit(1)

        # 5 - Testing credentials
        # Twilio Client setup for twilio
        account_sid = params.get(KEY_ACCOUNT_SID)
        auth_token = params.get(KEY_AUTH_TOKEN)
        self.test_client = Client(account_sid, auth_token)
        try:
            self.test_client.messages.list(limit=1)
        except Exception:
            logging.error(
                'Authorization failed. Please check your credentials.')
            sys.exit(1)

        # 6 - verify messaging service sid
        try:
            self.test_client.messaging.services(
                self.messaging_service_sid).fetch()
        except Exception:
            logging.error('Invalid [Messaging Service SID]')
            sys.exit(1)

    def run(self):
        '''
        Main execution code
        '''
        # Get proper list of tables
        in_tables = self.configuration.get_input_tables()
        in_table_names = self.get_tables(in_tables, 'input_mapping')
        logging.info("IN tables mapped: "+str(in_table_names))

        # Input Parameters
        params = self.cfg_params  # noqa
        account_sid = params.get(KEY_ACCOUNT_SID)
        auth_token = params.get(KEY_AUTH_TOKEN)
        self.messaging_service_sid = params.get(KEY_MESSAGING_SERVICE_SID)
        output_log_bool = bool(params.get(KEY_OUTPUT_LOG))
        today = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # validate user input parameters
        self.validate_user_params(params, in_tables)

        # Twilio Client setup for twilio
        self.twilio_client = Client(account_sid, auth_token)

        for table in in_tables:
            logging.info('Parsing table: {}'.format(table['destination']))

            for chunk in pd.read_csv(table['full_path'], chunksize=100, dtype=str):
                output_log = []
                for index, row in chunk.iterrows():
                    # logging.info(
                    #    'SENDING {} - {}'.format(row['phone_number'], row['message']))
                    success_bool = self.send_message(
                        phone=row['phone_number'], message_text=row['message'])

                    # Output Log file
                    log = {
                        'datetime': today,
                        'phone': row['phone_number'],
                        'message': row['message'],
                        'sent': '{}'.format(success_bool)
                    }
                    output_log.append(log)

                if output_log_bool:
                    self.output_log_file(output_log)

        logging.info("kds-team.app-twilio finished")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug = sys.argv[1]
    else:
        debug = True
    comp = Component(debug)
    comp.run()
