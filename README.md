# Royalty Enforcement example implementing ARC-0018


The enforcement of royalty payments is an important requirement for creators and businesses that derive their income from secondary sales. This example demonstrates how one might implement the Royalty Enforcement contract as well as presenting a marketplace that adheres to the spec and provides an interface for listing and selling an asset subject to a Royalty Policy.


## Running the demo

Install the [sandbox](https://github.com/algorand/sandbox) and start it in any private network mode (`dev`,`release`,etc..)

Clone this repository, initialize a virtual environment and install requirements
```sh
git clone git@github.com:algorand-devrel/royalty.git
cd royalty
python3 -m venv .venv
source .venv/bin/activate
pip install pyteal
```

Run the example
```sh
python main.py
```

You should see some printed statements from the methods defined in the ARC being called.

Comments on the specific calls an contracts are inline.


Happy hacking :)