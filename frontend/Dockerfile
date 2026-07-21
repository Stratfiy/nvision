FROM node:20-slim

WORKDIR /app
COPY package.json yarn.lock* ./
RUN corepack enable && yarn install --network-timeout 600000

COPY . .

EXPOSE 3000
ENV PORT=3000
CMD ["yarn", "start"]
