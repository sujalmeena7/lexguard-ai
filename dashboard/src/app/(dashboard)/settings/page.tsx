"use client";

import React from "react";
import { Settings, Bell, Shield, Moon } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function SettingsPage() {
  return (
    <ScrollArea className="h-full">
      <div className="p-6 space-y-6 max-w-3xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Settings className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Settings</h2>
            <p className="text-sm text-muted-foreground">Manage your account and dashboard preferences.</p>
          </div>
        </div>

        <Card className="glass-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-sm font-semibold">Notifications</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Email Alerts</p>
                <p className="text-xs text-muted-foreground">Receive audit completion and critical alerts via email.</p>
              </div>
              <Button variant="outline" size="sm" className="text-xs">Enabled</Button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Weekly Digest</p>
                <p className="text-xs text-muted-foreground">Summary of all audits and compliance changes.</p>
              </div>
              <Button variant="ghost" size="sm" className="text-xs">Disabled</Button>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-sm font-semibold">Security</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Two-Factor Authentication</p>
                <p className="text-xs text-muted-foreground">Add an extra layer of security to your account.</p>
              </div>
              <Button variant="outline" size="sm" className="text-xs">Setup</Button>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Moon className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-sm font-semibold">Appearance</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Theme settings are managed via the toggle in the top header.
            </p>
          </CardContent>
        </Card>
      </div>
    </ScrollArea>
  );
}
