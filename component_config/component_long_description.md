Twilio is the world's leading cloud communication platform that enables you to engage customers across channels - SMS, voice, video, WhatsApp, email and more.

This component allows users to send SMS messages programmatically to the phone numbers configured in the input table mapping. Send log will be available for the list of numbers this component is sending out.

### Configurations

The component is required to have at least one table in the input table mapping. If more the one tables are configured in the input table mapping, the component will loop through all of the input tables and process all the rows sending out the configured messages to the assigned numbers. 

#### Input Mapping Requirements
All tables are required to have the following columns
| Required Columns |
|-|
| phone_number |
| message |

#### Configuration Parameters
1. Account SID
    - Can be found in the Console
2. Authentication Token
    - Can be found in the Console
3. Messaging Service SID
    - Can be created via `Messaging Service` in the Console
    - The purpose of this service is to define the service identity
4. Output Log
    - Users have the options to output a log of the list of messages and targets sent out using this application.