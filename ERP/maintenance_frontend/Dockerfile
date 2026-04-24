FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

ENTRYPOINT ["npm", "run", "dev", "--", "--host"]
