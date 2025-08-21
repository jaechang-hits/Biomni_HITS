description = [
    {
        "description": "Executes the provided Python command in the notebook environment and returns the output.",
        "name": "run_python_repl",
        "optional_parameters": [],
        "required_parameters": [
            {
                "default": None,
                "description": "Python command to execute in the notebook environment",
                "name": "command",
                "type": "str",
            }
        ],
    },
    {
        "description": "Read the source code of a function from any module path.",
        "name": "read_function_source_code",
        "optional_parameters": [],
        "required_parameters": [
            {
                "default": None,
                "description": "Fully qualified function name "
                "(e.g., "
                "'bioagentos.tool.support_tools.write_python_code')",
                "name": "function_name",
                "type": "str",
            }
        ],
    },
    {
        "description": "Download data from Synapse using entity IDs. Requires SYNAPSE_AUTH_TOKEN environment variable for authentication. Automatically installs synapseclient if not available.",
        "name": "download_synapse_data",
        "optional_parameters": [
            {
                "name": "download_location",
                "type": "str",
                "description": "Directory where files will be downloaded",
                "default": ".",
            },
            {
                "name": "follow_link",
                "type": "bool",
                "description": "Whether to follow links to download the linked entity",
                "default": False,
            },
            {
                "name": "recursive",
                "type": "bool",
                "description": "Whether to recursively download folders and their contents",
                "default": False,
            },
            {
                "name": "timeout",
                "type": "int",
                "description": "Timeout in seconds for each download operation",
                "default": 300,
            },
        ],
        "required_parameters": [
            {
                "name": "entity_ids",
                "type": "str|list[str]",
                "description": "Synapse entity ID(s) to download (e.g., 'syn123456' or ['syn123', 'syn456'])",
                "default": None,
            }
        ],
    },
]
