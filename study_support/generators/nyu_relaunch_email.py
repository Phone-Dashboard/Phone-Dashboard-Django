# pylint: disable=line-too-long, no-member

def generator_name(identifier): # pylint: disable=unused-argument
    return 'NYU Study Relaunch E-Mail'

def extract_secondary_identifier(properties):
    if 'identifier' in properties:
        return properties['identifier']

    return None
