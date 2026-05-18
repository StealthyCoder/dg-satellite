# Performance Testing of dg-sat

This project serves as a simple way to benchmark/performance test the dg-satellite server you have either deployed or are running locally. 

It is based on :

 - \>= Python 3.12
 - \>= Locust 2.44

## How to run

Instructions on how to run the different scenarios and profiles.

## Overview

Overview of the two parameters you can experiment with.

headless vs web-ui

### Scenes

The scenes, the actual workflow of the worker that will be run. What will it do in what order.
In order to run them, maybe just write them all in Python, or change to a env + shell script approach.

### Profiles

The settings on how many workers, how long to wait for them to spawn, reset the counter to get a more accurate reading (cold start vs cached)
