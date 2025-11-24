// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

package api

import (
	"time"

	storage "github.com/foundriesio/dg-satellite/storage/api"
)

type daemonFunc func(stop chan bool)

type rolloutOptions struct {
	interval time.Duration
}

type Option func(*daemons)

// WithRolloverInterval sets the rollout rollover interval
func WithRolloverInterval(interval time.Duration) Option {
	return func(d *daemons) {
		d.rolloutOptions.interval = interval
	}
}

type daemons struct {
	context Context
	storage *storage.Storage
	daemons []daemonFunc
	stops   []chan bool

	rolloutOptions rolloutOptions
}

func NewDaemons(context Context, storage *storage.Storage, opts ...Option) *daemons {
	d := &daemons{context: context, storage: storage}
	d.rolloutOptions = rolloutOptions{
		interval: 5 * time.Minute,
	}
	d.daemons = []daemonFunc{
		d.rolloutWatchdog(true),
		d.rolloutWatchdog(false),
	}

	for _, opt := range opts {
		opt(d)
	}
	return d
}

func (d *daemons) Start() {
	for _, f := range d.daemons {
		stop := make(chan bool)
		d.stops = append(d.stops, stop)
		go f(stop)
	}
}

func (d *daemons) Shutdown() {
	for _, s := range d.stops {
		s <- true
	}
}
