FROM node:20-alpine

WORKDIR /app

# Copy dependency specifications
COPY package*.json ./

# Install dependencies (will install when package.json is mounted or copied)
RUN if [ -f package.json ]; then npm install; fi

# Copy application files
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "-p", "5173"]
