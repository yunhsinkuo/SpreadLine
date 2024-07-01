# SpreadLine Demo

We provide a simple web app to show how to set up and use SpreadLine. This web app is built with the help of [Vite](https://vitejs.dev/guide/) and [Flask](https://flask.palletsprojects.com/en/3.0.x/). We use vanilla JavaScript and Python.

## Setup

Please ensure the [node.js](https://nodejs.org/en/) version is either v14.18.0+ or v16.0.0+, which is required for Vite to work normally.

Please pip install SpreadLine package first. The instruction is provided in the main README.md.

Install npm packages.
```bash
cd ./frontend
npm install
```

Install python packages.
```bash
cd ./backend
pip install -r requirements.txt
```

To start the application, run
```
npm run start
```

You can then visit `localhost:5300` in the browser to see the interface.

*This has been tested with Node.js v19.3.0.