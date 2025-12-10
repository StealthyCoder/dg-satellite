// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: BSD-3-Clause-Clear

package main

import (
	"github.com/foundriesio/dg-satellite/storage"
)

type AuthInitCmd struct {
}

func (c AuthInitCmd) Run(args CommonArgs) error {
	fs, err := storage.NewFs(args.DataDir)
	if err != nil {
		return err
	}
	return fs.Auth.InitHmacSecret()
}
